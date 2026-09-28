#property strict
#include <Trade/Trade.mqh>

#define IMPULSE_TICK_CAPACITY 65536
#define IMPULSE_RETENTION_MSC 905000

input string StrategyServiceUrl = "http://127.0.0.1:1112/decision";
input string HealthcheckUrl = "http://127.0.0.1:1112/health";
input string TradeResultsUrl = "http://127.0.0.1:1112/api/trades";
input string CandleCacheUrl = "http://127.0.0.1:1112/api/candles";
input string LotusIngestApiKey = "";
input string ResultsBotId = "core-combined-v3";
input string StrategyBot1Id = "core-zigzag-v3";
input string StrategyBot2Id = "core-stochastic-v3";
input string StrategyBot3Id = "core-multitimeframe-v3";
input string StrategyBot4Id = "core-combined-v3";
// Deliberately empty. Set to one individual V3 only after demo validation.
// The combined V3 returns parallel candidates and requires a multi-order executor.
input string ExecutionBotId = "";
input string StrategySymbol = "XAUUSD";
input string StrategyTimeframe = "M5";
input int HistoryBars = 4000;
input int HistoryCacheBars = 100000;
input bool RefreshDeepHistoryOnInit = false;
// Export is read-only: it calls CopyTicksRange and writes a resumable local spool.
input bool EnableFusionHistoryExport = false;
input string FusionHistoryCollectorId = "2lotus-fusion-demo-history-v1";
input int FusionHistoryLookbackDays = 365;
input int FusionHistoryChunkMinutes = 60;
input int FusionHistoryChunkIntervalSeconds = 20;
input int PollIntervalSeconds = 5;
input int RequestTimeoutMs = 3000;
input bool EnableOrderExecution = false;
input bool EnableResultReporting = true;
input long StrategyMagicNumber = 20260720;

CTrade trade;
double lastBid = 0.0;
int upTicks = 0, downTicks = 0, neutralTicks = 0;
double upVolume = 0.0, downVolume = 0.0;
long impulseTimesMsc[IMPULSE_TICK_CAPACITY];
double impulseMids[IMPULSE_TICK_CAPACITY];
int impulseHead = 0;
int impulseCount = 0;
double dailyRealizedProfit = 0.0;
string brokerProfitDay = "";
bool fusionHistoryInitialized = false;
ulong fusionHistoryStartMsc = 0;
ulong fusionHistoryEndMsc = 0;
ulong fusionHistoryNextMsc = 0;
ulong fusionHistoryLastRunMsc = 0;
int fusionHistoryDataChunks = 0;
int fusionHistoryEmptyChunks = 0;

int OnInit()
{
   if(EnableOrderExecution && AccountInfoInteger(ACCOUNT_TRADE_MODE) != ACCOUNT_TRADE_MODE_DEMO)
   {
      Print("Order execution refused: this build is configured to trade only on an MT5 demo account.");
      return INIT_FAILED;
   }

   ENUM_TIMEFRAMES strategyPeriod = ResolveTimeframe(StrategyTimeframe);
   if(_Symbol != StrategySymbol || Period() != strategyPeriod)
   {
      PrintFormat("Switching operational chart from %s/%s to %s/%s", _Symbol, EnumToString((ENUM_TIMEFRAMES)Period()), StrategySymbol, StrategyTimeframe);
      if(!ChartSetSymbolPeriod(0, StrategySymbol, strategyPeriod))
      {
         PrintFormat("Unable to switch operational chart. Error=%d", GetLastError());
         return(INIT_FAILED);
      }
      return(INIT_SUCCEEDED);
   }
   EventSetTimer(PollIntervalSeconds);
   MarketBookAdd(_Symbol);
   trade.SetExpertMagicNumber(StrategyMagicNumber);
   CacheConfiguredBots();
   if(EnableFusionHistoryExport)
      InitializeFusionHistoryExport();
   PrintFormat(
      "SyncLeadBridgeEA initialized. ingest_key_configured=%s ingest_key_length=%d order_execution=%s execution_bot_configured=%s",
      LotusIngestApiKey != "" ? "true" : "false",
      StringLen(LotusIngestApiKey),
      EnableOrderExecution ? "true" : "false",
      ExecutionBotId != "" ? "true" : "false"
   );
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   MarketBookRelease(_Symbol);
}

void OnTick()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;
   RecordImpulseTick(tick);
   double volume = tick.volume_real > 0.0 ? tick.volume_real : 1.0;
   if(lastBid == 0.0 || tick.bid == lastBid) neutralTicks++;
   else if(tick.bid > lastBid) { upTicks++; upVolume += volume; }
   else { downTicks++; downVolume += volume; }
   lastBid = tick.bid;
}

void OnTradeTransaction(const MqlTradeTransaction &transaction, const MqlTradeRequest &request, const MqlTradeResult &result)
{
   if(!EnableResultReporting || transaction.type != TRADE_TRANSACTION_DEAL_ADD || transaction.deal == 0)
      return;

   ReportClosedDeal(transaction.deal);
}

void OnTimer()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      Print("Failed to read current tick for symbol ", _Symbol);
      return;
   }

   dailyRealizedProfit = CalculateRealizedProfitToday(brokerProfitDay);

   PollConfiguredBot(tick, StrategyBot1Id);
   if(StrategyBot2Id != StrategyBot1Id) PollConfiguredBot(tick, StrategyBot2Id);
   if(StrategyBot3Id != StrategyBot1Id && StrategyBot3Id != StrategyBot2Id) PollConfiguredBot(tick, StrategyBot3Id);
   if(StrategyBot4Id != StrategyBot1Id && StrategyBot4Id != StrategyBot2Id && StrategyBot4Id != StrategyBot3Id) PollConfiguredBot(tick, StrategyBot4Id);

   upTicks = downTicks = neutralTicks = 0;
   upVolume = downVolume = 0.0;
   RunFusionHistoryExportStep();
}

string FusionHistoryDirectory()
{
   return "2lotus-ticks\\" + FusionHistoryCollectorId;
}

string FusionHistoryStateFile()
{
   return FusionHistoryDirectory() + "\\history-state.txt";
}

ulong FusionHistoryChunkMsc()
{
   return (ulong)FusionHistoryChunkMinutes * 60000;
}

string ReadFusionHistoryStateValue(const int handle)
{
   string line = FileReadString(handle);
   int separator = StringFind(line, "=");
   return separator >= 0 ? StringSubstr(line, separator + 1) : "";
}

bool LoadFusionHistoryState()
{
   int handle = FileOpen(FusionHistoryStateFile(), FILE_READ|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return false;

   string version = ReadFusionHistoryStateValue(handle);
   string symbol = ReadFusionHistoryStateValue(handle);
   fusionHistoryStartMsc = (ulong)StringToInteger(ReadFusionHistoryStateValue(handle));
   fusionHistoryEndMsc = (ulong)StringToInteger(ReadFusionHistoryStateValue(handle));
   fusionHistoryNextMsc = (ulong)StringToInteger(ReadFusionHistoryStateValue(handle));
   fusionHistoryDataChunks = (int)StringToInteger(ReadFusionHistoryStateValue(handle));
   fusionHistoryEmptyChunks = (int)StringToInteger(ReadFusionHistoryStateValue(handle));
   FileClose(handle);

   return version == "1" && symbol == StrategySymbol && fusionHistoryStartMsc > 0 && fusionHistoryEndMsc > fusionHistoryStartMsc;
}

bool SaveFusionHistoryState()
{
   string directory = FusionHistoryDirectory();
   FolderCreate(directory, FILE_COMMON);
   string temporary = FusionHistoryStateFile() + ".part";
   int handle = FileOpen(temporary, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle == INVALID_HANDLE)
   {
      PrintFormat("Fusion history state open failed: error=%d", GetLastError());
      return false;
   }
   FileWriteString(handle, "version=1\r\n");
   FileWriteString(handle, "symbol=" + StrategySymbol + "\r\n");
   FileWriteString(handle, "start_msc=" + IntegerToString((long)fusionHistoryStartMsc) + "\r\n");
   FileWriteString(handle, "end_msc=" + IntegerToString((long)fusionHistoryEndMsc) + "\r\n");
   FileWriteString(handle, "next_msc=" + IntegerToString((long)fusionHistoryNextMsc) + "\r\n");
   FileWriteString(handle, "data_chunks=" + IntegerToString(fusionHistoryDataChunks) + "\r\n");
   FileWriteString(handle, "empty_chunks=" + IntegerToString(fusionHistoryEmptyChunks) + "\r\n");
   FileFlush(handle);
   FileClose(handle);
   if(!FileMove(temporary, FILE_COMMON, FusionHistoryStateFile(), FILE_COMMON|FILE_REWRITE))
   {
      PrintFormat("Fusion history state finalize failed: error=%d", GetLastError());
      return false;
   }
   return true;
}

void InitializeFusionHistoryExport()
{
   if(FusionHistoryLookbackDays < 1 || FusionHistoryChunkMinutes < 1 || FusionHistoryChunkMinutes > 1440 || FusionHistoryChunkIntervalSeconds < 1)
   {
      Print("Fusion history export disabled: invalid lookback, chunk, or interval input.");
      return;
   }
   if(!SymbolSelect(StrategySymbol, true))
   {
      PrintFormat("Fusion history export cannot select symbol=%s error=%d", StrategySymbol, GetLastError());
      return;
   }
   datetime serverNow = TimeTradeServer();
   if(serverNow <= 0)
   {
      Print("Fusion history export is waiting for the trade server clock.");
      return;
   }

   ulong nowMsc = (ulong)serverNow * 1000;
   ulong desiredStartMsc = nowMsc - (ulong)FusionHistoryLookbackDays * 86400000;
   ulong chunkMsc = FusionHistoryChunkMsc();
   bool resumed = LoadFusionHistoryState();
   if(!resumed || fusionHistoryNextMsc >= fusionHistoryEndMsc)
   {
      ulong overlapStartMsc = resumed && fusionHistoryEndMsc > chunkMsc ? fusionHistoryEndMsc - chunkMsc : desiredStartMsc;
      fusionHistoryStartMsc = overlapStartMsc > desiredStartMsc ? overlapStartMsc : desiredStartMsc;
      fusionHistoryEndMsc = nowMsc;
      fusionHistoryNextMsc = fusionHistoryStartMsc;
   }
   fusionHistoryInitialized = SaveFusionHistoryState();
   PrintFormat(
      "Fusion history export initialized: resumed=%s symbol=%s next_msc=%I64u end_msc=%I64u chunk_minutes=%d",
      resumed ? "true" : "false", StrategySymbol, fusionHistoryNextMsc, fusionHistoryEndMsc, FusionHistoryChunkMinutes
   );
}

bool WriteFusionHistoryEmptyMarker(const ulong fromMsc, const ulong toMsc)
{
   string name = FusionHistoryDirectory() + "\\" + StrategySymbol + "-history-" + IntegerToString((long)fromMsc) + "-" + IntegerToString((long)toMsc) + ".empty.txt";
   int handle = FileOpen(name, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return false;
   FileWriteString(handle, "source=Fusion Markets MT5\r\nstatus=empty\r\n");
   FileClose(handle);
   return true;
}

bool ExportFusionHistoryChunk(const ulong fromMsc, const ulong toMsc)
{
   MqlTick ticks[];
   ResetLastError();
   int count = CopyTicksRange(StrategySymbol, ticks, COPY_TICKS_ALL, fromMsc, toMsc);
   if(count < 0)
   {
      PrintFormat("Fusion history CopyTicksRange failed: from_msc=%I64u to_msc=%I64u error=%d", fromMsc, toMsc, GetLastError());
      return false;
   }
   if(count == 0)
   {
      if(!WriteFusionHistoryEmptyMarker(fromMsc, toMsc))
         return false;
      fusionHistoryEmptyChunks++;
      return true;
   }

   int digits = (int)SymbolInfoInteger(StrategySymbol, SYMBOL_DIGITS);
   double pointSize = SymbolInfoDouble(StrategySymbol, SYMBOL_POINT);
   string fileName = FusionHistoryDirectory() + "\\" + StrategySymbol + "-history-" + IntegerToString((long)fromMsc) + "-" + IntegerToString((long)toMsc) + ".part.csv";
   int handle = FileOpen(fileName, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ',');
   if(handle == INVALID_HANDLE)
   {
      PrintFormat("Fusion history spool open failed: file=%s error=%d", fileName, GetLastError());
      return false;
   }
   FileWrite(handle, "time_msc", "sequence", "bid", "ask", "last", "volume", "volume_real", "flags", "point_size");
   for(int index = 0; index < count; index++)
      FileWrite(handle, IntegerToString(ticks[index].time_msc), IntegerToString(index), DoubleToString(ticks[index].bid, digits), DoubleToString(ticks[index].ask, digits), DoubleToString(ticks[index].last, digits), IntegerToString((long)ticks[index].volume), DoubleToString(ticks[index].volume_real, 8), IntegerToString((int)ticks[index].flags), DoubleToString(pointSize, 10));
   FileFlush(handle);
   FileClose(handle);

   string readyName = fileName;
   StringReplace(readyName, ".part.csv", ".ready.csv");
   if(!FileMove(fileName, FILE_COMMON, readyName, FILE_COMMON|FILE_REWRITE))
   {
      PrintFormat("Fusion history spool finalize failed: file=%s error=%d", fileName, GetLastError());
      return false;
   }
   fusionHistoryDataChunks++;
   PrintFormat("Fusion history chunk exported: from_msc=%I64u to_msc=%I64u ticks=%d", fromMsc, toMsc, count);
   return true;
}

void RunFusionHistoryExportStep()
{
   if(!EnableFusionHistoryExport)
      return;
   if(!fusionHistoryInitialized)
   {
      InitializeFusionHistoryExport();
      return;
   }
   ulong nowMsc = GetTickCount64();
   if(fusionHistoryLastRunMsc > 0 && nowMsc - fusionHistoryLastRunMsc < (ulong)FusionHistoryChunkIntervalSeconds * 1000)
      return;
   fusionHistoryLastRunMsc = nowMsc;
   if(fusionHistoryNextMsc >= fusionHistoryEndMsc)
   {
      InitializeFusionHistoryExport();
      return;
   }
   ulong toMsc = fusionHistoryNextMsc + FusionHistoryChunkMsc() - 1;
   if(toMsc > fusionHistoryEndMsc)
      toMsc = fusionHistoryEndMsc;
   if(!ExportFusionHistoryChunk(fusionHistoryNextMsc, toMsc))
      return;
   fusionHistoryNextMsc = toMsc + 1;
   SaveFusionHistoryState();
}

void PollConfiguredBot(const MqlTick &tick, const string botId)
{
   if(botId == "") return;
   bool allowExecution = EnableOrderExecution && ExecutionBotId != "" && botId == ExecutionBotId;
   PollDecision(tick, botId, allowExecution);
}

void PollDecision(const MqlTick &tick, const string botId, const bool allowExecution)
{
   string payload = BuildDecisionPayload(tick, botId);
   string response = "";
   int status = PostJson(StrategyServiceUrl, payload, response);

   PrintFormat("Decision poll bot_id=%s status=%d response=%s", botId, status, response);

   if(status == 200 && allowExecution)
      TryExecuteDecision(response);
}

string BuildDecisionPayload(const MqlTick &tick, const string botId)
{
   MqlRates rates[];
   string request_id = StringFormat("%s-%s-%I64d-%u", botId, _Symbol, (long)TimeGMT(), GetTickCount());
   string timestamp_utc = ToIsoUtc(TimeGMT());
   double spread_points = (tick.ask - tick.bid) / _Point;
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin_free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double floatingProfit = AccountInfoDouble(ACCOUNT_PROFIT);
   long leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);
   long accountId = AccountInfoInteger(ACCOUNT_LOGIN);
   long accountTradeMode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
   string tradeMode = accountTradeMode == ACCOUNT_TRADE_MODE_DEMO ? "demo" :
                      accountTradeMode == ACCOUNT_TRADE_MODE_CONTEST ? "contest" : "real";
   string accountServer = AccountInfoString(ACCOUNT_SERVER);
   string accountBroker = AccountInfoString(ACCOUNT_COMPANY);
   string accountCurrency = AccountInfoString(ACCOUNT_CURRENCY);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double value_per_point_per_lot = 0.0;
   ENUM_TIMEFRAMES timeframe = ResolveTimeframe(StrategyTimeframe);
   int copied = CopyRates(_Symbol, timeframe, 1, HistoryBars, rates);

   if(tick_size > 0.0)
      value_per_point_per_lot = tick_value * (_Point / tick_size);

   if(copied <= 0)
      Print("Failed to copy rates for setup detection");

   string json =
      "{"
      "\"bot_id\":\"" + botId + "\","
      "\"request_id\":\"" + request_id + "\","
      "\"timestamp_utc\":\"" + timestamp_utc + "\","
      "\"symbol\":\"" + _Symbol + "\","
      "\"timeframe\":\"" + StrategyTimeframe + "\","
      "\"bid\":" + DoubleToString(tick.bid, _Digits) + ","
      "\"ask\":" + DoubleToString(tick.ask, _Digits) + ","
      "\"spread_points\":" + DoubleToString(spread_points, 2) + ","
      "\"point_size\":" + DoubleToString(_Point, _Digits) + ","
      "\"value_per_point_per_lot\":" + DoubleToString(value_per_point_per_lot, 6) + ","
      "\"candles\":" + SerializeRates(rates, copied) + ","
      "\"positions\":" + SerializePositions() + ","
      "\"account\":{"
         "\"balance\":" + DoubleToString(balance, 2) + ","
         "\"equity\":" + DoubleToString(equity, 2) + ","
         "\"margin_free\":" + DoubleToString(margin_free, 2) + ","
         "\"account_id\":" + IntegerToString(accountId) + ","
         "\"broker\":\"" + JsonEscape(accountBroker) + "\","
         "\"currency\":\"" + JsonEscape(accountCurrency) + "\","
         "\"floating_profit\":" + DoubleToString(floatingProfit, 2) + ","
         "\"realized_profit_today\":" + DoubleToString(dailyRealizedProfit, 2) + ","
         "\"profit_day\":\"" + brokerProfitDay + "\","
         "\"leverage\":" + IntegerToString((int)leverage) + ","
         "\"trade_mode\":\"" + tradeMode + "\","
         "\"server\":\"" + JsonEscape(accountServer) + "\"" +
      "},"
      "\"indicators\":" + SerializeImpulseIndicators(tick) +
      ",\"flow\":{"
         "\"book\":" + SerializeBook() + ","
         "\"up_ticks\":" + IntegerToString(upTicks) + ","
         "\"down_ticks\":" + IntegerToString(downTicks) + ","
         "\"neutral_ticks\":" + IntegerToString(neutralTicks) + ","
         "\"up_volume\":" + DoubleToString(upVolume, 2) + ","
         "\"down_volume\":" + DoubleToString(downVolume, 2) +
      "}"
      "}";

   return json;
}

string JsonEscape(string value)
{
   StringReplace(value, "\\", "\\\\");
   StringReplace(value, "\"", "\\\"");
   StringReplace(value, "\r", "\\r");
   StringReplace(value, "\n", "\\n");
   return value;
}

double CalculateRealizedProfitToday(string &profitDay)
{
   datetime serverNow = TimeTradeServer();
   MqlDateTime day;
   TimeToStruct(serverNow, day);
   profitDay = StringFormat("%04d-%02d-%02d", day.year, day.mon, day.day);
   day.hour = 0;
   day.min = 0;
   day.sec = 0;
   if(!HistorySelect(StructToTime(day), serverNow))
      return 0.0;

   double realized = 0.0;
   for(int index = 0; index < HistoryDealsTotal(); index++)
   {
      ulong ticket = HistoryDealGetTicket(index);
      if(ticket == 0) continue;
      ENUM_DEAL_TYPE type = (ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL)
         continue;
      realized += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                + HistoryDealGetDouble(ticket, DEAL_COMMISSION)
                + HistoryDealGetDouble(ticket, DEAL_SWAP)
                + HistoryDealGetDouble(ticket, DEAL_FEE);
   }
   return realized;
}

void RecordImpulseTick(const MqlTick &tick)
{
   long timeMsc = tick.time_msc;
   double mid = (tick.bid + tick.ask) / 2.0;
   int writeIndex = (impulseHead + impulseCount) % IMPULSE_TICK_CAPACITY;
   if(impulseCount == IMPULSE_TICK_CAPACITY)
   {
      writeIndex = impulseHead;
      impulseHead = (impulseHead + 1) % IMPULSE_TICK_CAPACITY;
   }
   else
      impulseCount++;

   impulseTimesMsc[writeIndex] = timeMsc;
   impulseMids[writeIndex] = mid;

   long cutoff = timeMsc - IMPULSE_RETENTION_MSC;
   while(impulseCount > 0 && impulseTimesMsc[impulseHead] < cutoff)
   {
      impulseHead = (impulseHead + 1) % IMPULSE_TICK_CAPACITY;
      impulseCount--;
   }
}

bool GetImpulseWindow(const MqlTick &tick, const int seconds, double &movePoints, int &tickCount, double &tickRate)
{
   movePoints = 0.0;
   tickCount = 0;
   tickRate = 0.0;
   if(impulseCount < 2 || _Point <= 0.0)
      return false;

   long targetMsc = tick.time_msc - (long)seconds * 1000;
   if(impulseTimesMsc[impulseHead] > targetMsc)
      return false;

   int referenceOffset = -1;
   for(int offset = 0; offset < impulseCount; offset++)
   {
      int index = (impulseHead + offset) % IMPULSE_TICK_CAPACITY;
      if(impulseTimesMsc[index] >= targetMsc)
      {
         referenceOffset = offset;
         break;
      }
   }
   if(referenceOffset < 0)
      return false;

   int referenceIndex = (impulseHead + referenceOffset) % IMPULSE_TICK_CAPACITY;
   double currentMid = (tick.bid + tick.ask) / 2.0;
   movePoints = (currentMid - impulseMids[referenceIndex]) / _Point;
   tickCount = impulseCount - referenceOffset;
   tickRate = (double)tickCount / seconds;
   return true;
}

double GetMicroEfficiency(const MqlTick &tick, const int seconds)
{
   double movePoints = 0.0, tickRate = 0.0;
   int tickCount = 0;
   if(!GetImpulseWindow(tick, seconds, movePoints, tickCount, tickRate) || tickCount < 2)
      return 0.0;
   int firstOffset = impulseCount - tickCount;
   double path = 0.0;
   double previous = impulseMids[(impulseHead + firstOffset) % IMPULSE_TICK_CAPACITY];
   for(int offset = firstOffset + 1; offset < impulseCount; offset++)
   {
      double current = impulseMids[(impulseHead + offset) % IMPULSE_TICK_CAPACITY];
      path += MathAbs(current - previous);
      previous = current;
   }
   double currentMid = (tick.bid + tick.ask) / 2.0;
   path += MathAbs(currentMid - previous);
   return path > 0.0 ? MathAbs(movePoints * _Point) / path : 0.0;
}

string SerializeImpulseWindow(const MqlTick &tick, const int seconds)
{
   double movePoints = 0.0, tickRate = 0.0;
   int tickCount = 0;
   bool ready = GetImpulseWindow(tick, seconds, movePoints, tickCount, tickRate);
   string prefix = "impulse_" + IntegerToString(seconds) + "s_";
   return
      "\"" + prefix + "ready\":" + (ready ? "1" : "0") + "," +
      "\"" + prefix + "move_points\":" + DoubleToString(movePoints, 6) + "," +
      "\"" + prefix + "tick_count\":" + IntegerToString(tickCount) + "," +
      "\"" + prefix + "tick_rate_per_second\":" + DoubleToString(tickRate, 6);
}

string SerializeImpulseIndicators(const MqlTick &tick)
{
   double move5 = 0.0, rate5 = 0.0, move10 = 0.0, rate10 = 0.0;
   int count5 = 0, count10 = 0;
   GetImpulseWindow(tick, 5, move5, count5, rate5);
   GetImpulseWindow(tick, 10, move10, count10, rate10);
   double acceleration = rate10 > 0.0 ? rate5 / rate10 : 0.0;
   return
      "{" +
      SerializeImpulseWindow(tick, 5) + "," +
      SerializeImpulseWindow(tick, 10) + "," +
      SerializeImpulseWindow(tick, 30) + "," +
      SerializeImpulseWindow(tick, 60) + "," +
      SerializeImpulseWindow(tick, 300) + "," +
      SerializeImpulseWindow(tick, 900) + "," +
      "\"micro_30s_efficiency\":" + DoubleToString(GetMicroEfficiency(tick, 30), 6) + "," +
      "\"micro_tick_acceleration_5s_vs_10s\":" + DoubleToString(acceleration, 6) +
      "}";
}

void CacheConfiguredBots()
{
   // OHLCV belongs to the market, not to a strategy. Keep one deep canonical
   // history per symbol and let every bot for that market reuse it.
   if(RefreshDeepHistoryOnInit)
      CacheHistory(StrategySymbol, ResultsBotId);
   else
      Print("Deep history refresh skipped; set RefreshDeepHistoryOnInit=true for an explicit bootstrap.");
}

bool CacheHistory(const string symbol, const string botId)
{
   if(symbol == "" || botId == "")
      return true;
   if(!SymbolSelect(symbol, true))
   {
      PrintFormat("Unable to select history symbol=%s error=%d", symbol, GetLastError());
      return false;
   }
   MqlRates rates[];
   // Existing charts retain their saved inputs across recompiles. Enforce the
   // canonical-history floor even when an older chart still has 2000 configured.
   int requestedBars = HistoryCacheBars < 100000 ? 100000 : HistoryCacheBars;
   int copied = CopyRates(symbol, ResolveTimeframe(StrategyTimeframe), 1, requestedBars, rates);
   if(copied <= 0) { PrintFormat("No history available for cache symbol=%s.", symbol); return false; }
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   bool allBatchesSucceeded = true;
   for(int start = 0; start < copied; start += 1000)
   {
      int count = MathMin(1000, copied - start);
      string payload = "{\"bot_id\":\"" + botId + "\",\"symbol\":\"" + symbol + "\",\"timeframe\":\"" + StrategyTimeframe + "\",\"candles\":" + SerializeRatesRangeWithDigits(rates, start, count, digits) + "}";
      string response = "";
      int status = PostJson(CandleCacheUrl, payload, response);
      if(status < 200 || status >= 300)
         allBatchesSucceeded = false;
      PrintFormat("History cache bot_id=%s symbol=%s batch start=%d count=%d status=%d", botId, symbol, start, count, status);
   }
   bool coversYear = rates[0].time <= TimeTradeServer() - 360 * 24 * 60 * 60;
   PrintFormat("History cache complete bot_id=%s symbol=%s copied=%d covers_year=%s", botId, symbol, copied, coversYear ? "true" : "false");
   return coversYear && allBatchesSucceeded;
}

string SerializePositions()
{
   string json = "[";
   for(int index = 0; index < PositionsTotal(); index++)
   {
      ulong ticket = PositionGetTicket(index);
      if(ticket == 0 || !PositionSelectByTicket(ticket)) continue;
      string symbol = PositionGetString(POSITION_SYMBOL);
      ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
      string side = type == POSITION_TYPE_BUY ? "buy" : "sell";
      int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      if(json != "[") json += ",";
      json += "{"
         "\"symbol\":\"" + symbol + "\","
         "\"side\":\"" + side + "\","
         "\"volume\":" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ","
         "\"entry_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), digits) + ","
         "\"profit\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2)
      + "}";
   }
   return json + "]";
}

string SerializeBook()
{
   MqlBookInfo levels[];
   if(!MarketBookGet(_Symbol, levels)) return "[]";
   string json = "[";
   int bidCount = 0, askCount = 0;
   for(int i = 0; i < ArraySize(levels); i++)
   {
      string side = "";
      if(levels[i].type == BOOK_TYPE_BUY && bidCount++ < 5) side = "bid";
      if(levels[i].type == BOOK_TYPE_SELL && askCount++ < 5) side = "ask";
      if(side == "") continue;
      if(json != "[") json += ",";
      json += "{\"side\":\"" + side + "\",\"price\":" + DoubleToString(levels[i].price, _Digits) + ",\"volume\":" + DoubleToString(levels[i].volume, 2) + "}";
   }
   return json + "]";
}

int PostJson(const string url, const string payload, string &responseText)
{
   string headers = "Content-Type: application/json\r\n";
   if(LotusIngestApiKey != "")
      headers += "X-2Lotus-Ingest-Key: " + LotusIngestApiKey + "\r\n";
   return PostJsonWithHeaders(url, payload, headers, responseText);
}

int PostJsonWithHeaders(const string url, const string payload, const string headers, string &responseText)
{
   char requestBody[];
   char responseBody[];
   string responseHeaders = "";

   StringToCharArray(payload, requestBody, 0, StringLen(payload), CP_UTF8);
   int status = WebRequest("POST", url, headers, RequestTimeoutMs, requestBody, responseBody, responseHeaders);

   if(status == -1)
   {
      int errorCode = GetLastError();
      responseText = StringFormat("WebRequest failed: %d", errorCode);
      ResetLastError();
      return status;
   }

   responseText = CharArrayToString(responseBody, 0, -1, CP_UTF8);
   return status;
}

void ReportClosedDeal(const ulong closingDeal)
{
   if(LotusIngestApiKey == "")
   {
      Print("Trade result was not reported: LotusIngestApiKey is empty.");
      return;
   }

   ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(closingDeal, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_OUT_BY)
      return;

   ulong positionId = (ulong)HistoryDealGetInteger(closingDeal, DEAL_POSITION_ID);
   if(positionId == 0 || !HistorySelectByPosition(positionId))
   {
      PrintFormat("Could not load history for position %I64u", positionId);
      return;
   }

   ulong openingDeal = 0;
   int dealCount = HistoryDealsTotal();
   for(int index = 0; index < dealCount; index++)
   {
      ulong candidate = HistoryDealGetTicket(index);
      if(candidate == 0)
         continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(candidate, DEAL_ENTRY) == DEAL_ENTRY_IN)
      {
         openingDeal = candidate;
         break;
      }
   }

   if(openingDeal == 0)
   {
      PrintFormat("Could not find opening deal for position %I64u", positionId);
      return;
   }

   ENUM_DEAL_TYPE openingType = (ENUM_DEAL_TYPE)HistoryDealGetInteger(openingDeal, DEAL_TYPE);
   string side = openingType == DEAL_TYPE_BUY ? "buy" : "sell";
   string symbol = HistoryDealGetString(closingDeal, DEAL_SYMBOL);
   double grossProfit = HistoryDealGetDouble(closingDeal, DEAL_PROFIT) + HistoryDealGetDouble(closingDeal, DEAL_SWAP);
   double commission = HistoryDealGetDouble(closingDeal, DEAL_COMMISSION);
   double fees = commission < 0.0 ? -commission : 0.0;
   double netProfit = grossProfit + commission;
   datetime openedAt = (datetime)HistoryDealGetInteger(openingDeal, DEAL_TIME);
   datetime closedAt = (datetime)HistoryDealGetInteger(closingDeal, DEAL_TIME);

   string tradePayload =
      "{"
      "\"bot_id\":\"" + ResultsBotId + "\","
      "\"trade\":{"
         "\"trade_id\":\"mt5-" + IntegerToString((long)closingDeal) + "\","
         "\"symbol\":\"" + symbol + "\","
         "\"timeframe\":\"" + StrategyTimeframe + "\","
         "\"setup\":\"mt5_closed_trade\","
         "\"side\":\"" + side + "\","
         "\"opened_at_utc\":\"" + ServerTimeToIsoUtc(openedAt) + "\","
         "\"closed_at_utc\":\"" + ServerTimeToIsoUtc(closedAt) + "\","
         "\"volume_lots\":" + DoubleToString(HistoryDealGetDouble(closingDeal, DEAL_VOLUME), 2) + ","
         "\"entry_price\":" + DoubleToString(HistoryDealGetDouble(openingDeal, DEAL_PRICE), _Digits) + ","
         "\"exit_price\":" + DoubleToString(HistoryDealGetDouble(closingDeal, DEAL_PRICE), _Digits) + ","
         "\"risk_amount\":0,"
         "\"gross_pnl\":" + DoubleToString(grossProfit, 2) + ","
         "\"fees\":" + DoubleToString(fees, 2) + ","
         "\"net_pnl\":" + DoubleToString(netProfit, 2) + ","
         "\"note\":\"MT5 closing deal " + IntegerToString((long)closingDeal) + "\""
      "}"
      "}";

   string response = "";
   string headers = "Content-Type: application/json\r\nX-2Lotus-Ingest-Key: " + LotusIngestApiKey + "\r\n";
   int status = PostJsonWithHeaders(TradeResultsUrl, tradePayload, headers, response);
   PrintFormat("Trade result report deal=%I64u status=%d response=%s", closingDeal, status, response);
}

string ToIsoUtc(const datetime value)
{
   string formatted = TimeToString(value, TIME_DATE|TIME_SECONDS);
   StringReplace(formatted, ".", "-");
   StringReplace(formatted, " ", "T");
   return formatted + "Z";
}

string ServerTimeToIsoUtc(const datetime value)
{
   int serverOffsetSeconds = (int)(TimeTradeServer() - TimeGMT());
   return ToIsoUtc(value - serverOffsetSeconds);
}

void TryExecuteDecision(const string response)
{
   string action = ExtractJsonString(response, "action");
   string reason = ExtractJsonString(response, "reason");
   double size = ExtractJsonNumber(response, "size");
   double stopLoss = ExtractJsonNumber(response, "stop_loss_price");
   double takeProfit = ExtractJsonNumber(response, "take_profit_price");

   if(action == "hold" || action == "")
   {
      PrintFormat("No execution. action=%s reason=%s", action, reason);
      return;
   }

   if(PositionSelect(_Symbol))
   {
      PrintFormat("Position already open for %s. Skipping new execution.", _Symbol);
      return;
   }

   double volume = NormalizeVolume(size);
   if(volume <= 0.0)
   {
      PrintFormat("Invalid volume from service. raw=%f normalized=%f", size, volume);
      return;
   }

   bool result = false;
   if(action == "buy")
      result = trade.Buy(volume, _Symbol, 0.0, stopLoss, takeProfit, "SyncLead auto buy");
   else if(action == "sell")
      result = trade.Sell(volume, _Symbol, 0.0, stopLoss, takeProfit, "SyncLead auto sell");
   else
      return;

   if(!result)
   {
      PrintFormat(
         "OrderSend failed. action=%s volume=%f retcode=%d description=%s",
         action,
         volume,
         trade.ResultRetcode(),
         trade.ResultRetcodeDescription()
      );
      return;
   }

   PrintFormat(
      "Order executed. action=%s volume=%f order=%I64d deal=%I64d reason=%s",
      action,
      volume,
      trade.ResultOrder(),
      trade.ResultDeal(),
      reason
   );
}

ENUM_TIMEFRAMES ResolveTimeframe(const string tf)
{
   if(tf == "M1")
      return PERIOD_M1;
   if(tf == "M5")
      return PERIOD_M5;
   if(tf == "M15")
      return PERIOD_M15;
   if(tf == "H1")
      return PERIOD_H1;

   return PERIOD_M5;
}

string SerializeRates(MqlRates &rates[], const int count)
{
   return SerializeRatesRange(rates, 0, count);
}

string SerializeRatesRange(MqlRates &rates[], const int start, const int count)
{
   return SerializeRatesRangeWithDigits(rates, start, count, _Digits);
}

string SerializeRatesRangeWithDigits(MqlRates &rates[], const int start, const int count, const int digits)
{
   string json = "[";

   for(int i = start; i < start + count; i++)
   {
      if(i > start)
         json += ",";

      json += "{"
         "\"timestamp_utc\":\"" + ServerTimeToIsoUtc(rates[i].time) + "\","
         "\"open\":" + DoubleToString(rates[i].open, digits) + ","
         "\"high\":" + DoubleToString(rates[i].high, digits) + ","
         "\"low\":" + DoubleToString(rates[i].low, digits) + ","
         "\"close\":" + DoubleToString(rates[i].close, digits) + ","
         "\"volume\":" + IntegerToString((int)rates[i].tick_volume)
      + "}";
   }

   json += "]";
   return json;
}

double NormalizeVolume(const double requestedVolume)
{
   double minVolume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxVolume = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(step <= 0.0)
      step = minVolume;

   double bounded = MathMax(minVolume, MathMin(maxVolume, requestedVolume));
   double normalized = MathFloor(bounded / step) * step;

   return NormalizeDouble(normalized, 2);
}

string ExtractJsonString(const string json, const string key)
{
   string token = "\"" + key + "\":\"";
   int start = StringFind(json, token);
   if(start < 0)
      return "";

   start += StringLen(token);
   int end = StringFind(json, "\"", start);
   if(end < 0)
      return "";

   return StringSubstr(json, start, end - start);
}

double ExtractJsonNumber(const string json, const string key)
{
   string token = "\"" + key + "\":";
   int start = StringFind(json, token);
   if(start < 0)
      return 0.0;

   start += StringLen(token);
   int end = start;
   int len = StringLen(json);

   while(end < len)
   {
      ushort ch = StringGetCharacter(json, end);
      if(ch == ',' || ch == '}' || ch == ']')
         break;
      end++;
   }

   string raw = StringSubstr(json, start, end - start);
   StringTrimLeft(raw);
   StringTrimRight(raw);
   if(raw == "null" || raw == "")
      return 0.0;

   return StringToDouble(raw);
}
