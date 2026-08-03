#property strict
#include <Trade/Trade.mqh>

input string StrategyServiceUrl = "http://127.0.0.1:8000/decision";
input string HealthcheckUrl = "http://127.0.0.1:8000/health";
input string TradeResultsUrl = "http://127.0.0.1:8000/api/trades";
input string CandleCacheUrl = "http://127.0.0.1:8000/api/candles";
input string LotusIngestApiKey = "";
input string ResultsBotId = "bot-6";
input string ShadowBotIds = "bot-2,bot-3,bot-4,bot-5";
input string ExperimentalBotId = "bot-6";
input string MultitimeframeResearchBotId = "bot-7";
input string PortfolioResearchBotId = "bot-8";
input string AdaptivePortfolioResearchBotId = "bot-9";
input string BalancedPortfolioResearchBotId = "bot-10";
input string AggressivePortfolioResearchBotId = "bot-11";
input string HappyGoldResearchBotId = "bot-12";
input string HappyGoldConfirmedResearchBotId = "bot-13";
input string HappyGoldMicrostructureResearchBotId = "bot-14";
input string EurUsdRegimeConfirmedBotId = "bot-eur-13";
input string BitcoinRegimeConfirmedBotId = "";
input string StrategySymbol = "XAUUSD";
input string SecondaryHistorySymbol = "EURUSD";
input string SecondaryHistoryBotId = "bot-eur-1";
input string BitcoinHistorySymbol = "BTCUSD";
input string BitcoinHistoryBotId = "bot-btc-13";
input string StrategyTimeframe = "M5";
input int HistoryBars = 60;
input int HistoryCacheBars = 100000;
input bool RefreshDeepHistoryOnInit = false;
input bool RefreshSecondaryHistoryOnInit = false;
input bool RefreshBitcoinHistoryOnInit = false;
input int PollIntervalSeconds = 5;
input int MicrostructurePollIntervalSeconds = 1;
input int RequestTimeoutMs = 3000;
input bool EnableOrderExecution = false;
input bool EnableResultReporting = true;
input long StrategyMagicNumber = 20260720;

CTrade trade;
double lastBid = 0.0;
int upTicks = 0, downTicks = 0, neutralTicks = 0;
double upVolume = 0.0, downVolume = 0.0;
bool secondaryHistoryReady = false;
int secondaryHistoryAttempts = 0;
string secondaryHistoryCacheKey = "";
bool bitcoinHistoryReady = false;
int bitcoinHistoryAttempts = 0;
string bitcoinHistoryCacheKey = "";
datetime lastStandardPollAt = 0;
datetime lastMicrostructurePollAt = 0;

int OnInit()
{
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
   EventSetTimer(MathMax(1, MathMin(PollIntervalSeconds, MicrostructurePollIntervalSeconds)));
   MarketBookAdd(_Symbol);
   trade.SetExpertMagicNumber(StrategyMagicNumber);
   CacheConfiguredBots();
   Print("SyncLeadBridgeEA initialized. Add the service URLs to MT5 WebRequest allowlist.");
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
   if(RefreshSecondaryHistoryOnInit && !secondaryHistoryReady && secondaryHistoryAttempts < 6)
   {
      secondaryHistoryAttempts++;
      secondaryHistoryReady = CacheHistory(SecondaryHistorySymbol, SecondaryHistoryBotId);
      if(secondaryHistoryReady && secondaryHistoryCacheKey != "")
         GlobalVariableSet(secondaryHistoryCacheKey, (double)TimeGMT());
   }
   if(RefreshBitcoinHistoryOnInit && !bitcoinHistoryReady && bitcoinHistoryAttempts < 12)
   {
      bitcoinHistoryAttempts++;
      bitcoinHistoryReady = CacheHistory(BitcoinHistorySymbol, BitcoinHistoryBotId);
      if(bitcoinHistoryReady && bitcoinHistoryCacheKey != "")
         GlobalVariableSet(bitcoinHistoryCacheKey, (double)TimeGMT());
   }

   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      Print("Failed to read current tick for symbol ", _Symbol);
      return;
   }

   datetime nowUtc = TimeGMT();
   bool pollStandard = lastStandardPollAt == 0 || nowUtc - lastStandardPollAt >= PollIntervalSeconds;
   bool pollMicrostructure = lastMicrostructurePollAt == 0 || nowUtc - lastMicrostructurePollAt >= MicrostructurePollIntervalSeconds;

   // The active research portfolio is intentionally restricted to Bots 6, 7,
   // 11, 12, 13 and 14. Legacy inputs remain declared so existing chart presets load,
   // but they no longer cause archived strategies to be polled.
   if(pollStandard && ExperimentalBotId != "")
      PollDecision(tick, ExperimentalBotId, false);
   if(pollStandard && MultitimeframeResearchBotId != "" && MultitimeframeResearchBotId != ExperimentalBotId)
      PollDecision(tick, MultitimeframeResearchBotId, false);
   if(pollStandard && AggressivePortfolioResearchBotId != "" && AggressivePortfolioResearchBotId != ExperimentalBotId && AggressivePortfolioResearchBotId != MultitimeframeResearchBotId)
      PollDecision(tick, AggressivePortfolioResearchBotId, false);
   if(pollStandard && HappyGoldResearchBotId != "" && HappyGoldResearchBotId != ExperimentalBotId && HappyGoldResearchBotId != MultitimeframeResearchBotId && HappyGoldResearchBotId != AggressivePortfolioResearchBotId)
      PollDecision(tick, HappyGoldResearchBotId, false);
   if(pollStandard && HappyGoldConfirmedResearchBotId != "" && HappyGoldConfirmedResearchBotId != ExperimentalBotId && HappyGoldConfirmedResearchBotId != MultitimeframeResearchBotId && HappyGoldConfirmedResearchBotId != AggressivePortfolioResearchBotId && HappyGoldConfirmedResearchBotId != HappyGoldResearchBotId)
      PollDecision(tick, HappyGoldConfirmedResearchBotId, false);
   if(pollStandard && EurUsdRegimeConfirmedBotId != "")
      PollDecisionForSymbol(SecondaryHistorySymbol, EurUsdRegimeConfirmedBotId);
   if(pollStandard && BitcoinRegimeConfirmedBotId != "")
      PollDecisionForSymbol(BitcoinHistorySymbol, BitcoinRegimeConfirmedBotId);
   if(pollMicrostructure && HappyGoldMicrostructureResearchBotId != "" && HappyGoldMicrostructureResearchBotId != ExperimentalBotId && HappyGoldMicrostructureResearchBotId != MultitimeframeResearchBotId && HappyGoldMicrostructureResearchBotId != AggressivePortfolioResearchBotId && HappyGoldMicrostructureResearchBotId != HappyGoldResearchBotId && HappyGoldMicrostructureResearchBotId != HappyGoldConfirmedResearchBotId)
      PollDecision(tick, HappyGoldMicrostructureResearchBotId, false);

   if(pollStandard)
      lastStandardPollAt = nowUtc;
   if(pollMicrostructure)
   {
      lastMicrostructurePollAt = nowUtc;
      upTicks = downTicks = neutralTicks = 0;
      upVolume = downVolume = 0.0;
   }
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
   MqlRates microRates[];
   string request_id = StringFormat("%s-%s-%u", botId, _Symbol, GetTickCount());
   string timestamp_utc = ToIsoUtc(TimeGMT());
   double spread_points = (tick.ask - tick.bid) / _Point;
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   double margin_free = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   long leverage = AccountInfoInteger(ACCOUNT_LEVERAGE);
   double tick_value = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tick_size = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double value_per_point_per_lot = 0.0;
   ENUM_TIMEFRAMES timeframe = ResolveTimeframe(StrategyTimeframe);
   int copied = CopyRates(_Symbol, timeframe, 1, HistoryBars, rates);
   int microCopied = CopyRates(_Symbol, PERIOD_M1, 1, 20, microRates);

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
      "\"micro_candles\":" + SerializeRates(microRates, microCopied) + ","
      "\"positions\":[],"
      "\"account\":{"
         "\"balance\":" + DoubleToString(balance, 2) + ","
         "\"equity\":" + DoubleToString(equity, 2) + ","
         "\"margin_free\":" + DoubleToString(margin_free, 2) + ","
         "\"leverage\":" + IntegerToString((int)leverage) +
      "},"
      "\"indicators\":{}" +
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

void PollDecisionForSymbol(const string symbol, const string botId)
{
   if(symbol == "" || botId == "") return;
   if(!SymbolSelect(symbol, true))
   {
      PrintFormat("Decision poll skipped bot_id=%s symbol=%s reason=symbol_unavailable error=%d", botId, symbol, GetLastError());
      return;
   }
   MqlTick tick;
   if(!SymbolInfoTick(symbol, tick))
   {
      PrintFormat("Decision poll skipped bot_id=%s symbol=%s reason=tick_unavailable error=%d", botId, symbol, GetLastError());
      return;
   }
   string response = "";
   int status = PostJson(StrategyServiceUrl, BuildDecisionPayloadForSymbol(symbol, tick, botId), response);
   PrintFormat("Decision poll bot_id=%s symbol=%s status=%d response=%s", botId, symbol, status, response);
}

string BuildDecisionPayloadForSymbol(const string symbol, const MqlTick &tick, const string botId)
{
   MqlRates rates[];
   ENUM_TIMEFRAMES timeframe = ResolveTimeframe(StrategyTimeframe);
   int copied = CopyRates(symbol, timeframe, 1, HistoryBars, rates);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   double tickValue = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
   double valuePerPointPerLot = tickSize > 0.0 ? tickValue * (point / tickSize) : 0.0;
   double spreadPoints = point > 0.0 ? (tick.ask - tick.bid) / point : 0.0;
   string requestId = StringFormat("%s-%s-%u", botId, symbol, GetTickCount());
   if(copied <= 0)
      PrintFormat("Failed to copy rates bot_id=%s symbol=%s error=%d", botId, symbol, GetLastError());
   return
      "{"
      "\"bot_id\":\"" + botId + "\","
      "\"request_id\":\"" + requestId + "\","
      "\"timestamp_utc\":\"" + ToIsoUtc(TimeGMT()) + "\","
      "\"symbol\":\"" + symbol + "\","
      "\"timeframe\":\"" + StrategyTimeframe + "\","
      "\"bid\":" + DoubleToString(tick.bid, digits) + ","
      "\"ask\":" + DoubleToString(tick.ask, digits) + ","
      "\"spread_points\":" + DoubleToString(spreadPoints, 2) + ","
      "\"point_size\":" + DoubleToString(point, digits) + ","
      "\"value_per_point_per_lot\":" + DoubleToString(valuePerPointPerLot, 6) + ","
      "\"candles\":" + SerializeRatesRangeWithDigits(rates, 0, copied, digits) + ","
      "\"micro_candles\":[],"
      "\"positions\":[],"
      "\"account\":{" +
         "\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ","
         "\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ","
         "\"margin_free\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + ","
         "\"leverage\":" + IntegerToString((int)AccountInfoInteger(ACCOUNT_LEVERAGE)) +
      "},"
      "\"indicators\":{},"
      "\"flow\":{\"book\":[],\"up_ticks\":0,\"down_ticks\":0,\"neutral_ticks\":0,\"up_volume\":0,\"down_volume\":0}"
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
   if(RefreshSecondaryHistoryOnInit)
   {
      secondaryHistoryCacheKey = "2LotusHistory_" + SecondaryHistorySymbol + "_" + StrategyTimeframe;
      if(GlobalVariableCheck(secondaryHistoryCacheKey))
      {
         secondaryHistoryReady = true;
         PrintFormat("Secondary history already bootstrapped symbol=%s at=%s", SecondaryHistorySymbol, TimeToString((datetime)GlobalVariableGet(secondaryHistoryCacheKey), TIME_DATE|TIME_SECONDS));
      }
      else
      {
         SymbolSelect(SecondaryHistorySymbol, true);
         PrintFormat("Secondary history refresh scheduled symbol=%s bot_id=%s", SecondaryHistorySymbol, SecondaryHistoryBotId);
      }
   }
   if(RefreshBitcoinHistoryOnInit)
   {
      bitcoinHistoryCacheKey = "2LotusHistory_" + BitcoinHistorySymbol + "_" + StrategyTimeframe;
      if(GlobalVariableCheck(bitcoinHistoryCacheKey))
      {
         bitcoinHistoryReady = true;
         PrintFormat("Bitcoin history already bootstrapped symbol=%s at=%s", BitcoinHistorySymbol, TimeToString((datetime)GlobalVariableGet(bitcoinHistoryCacheKey), TIME_DATE|TIME_SECONDS));
      }
      else
      {
         SymbolSelect(BitcoinHistorySymbol, true);
         PrintFormat("Bitcoin history refresh scheduled symbol=%s bot_id=%s", BitcoinHistorySymbol, BitcoinHistoryBotId);
      }
   }
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
