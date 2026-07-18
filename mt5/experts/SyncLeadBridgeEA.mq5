#property strict
#include <Trade/Trade.mqh>

input string StrategyServiceUrl = "http://127.0.0.1:8000/decision";
input string HealthcheckUrl = "http://127.0.0.1:8000/health";
input string StrategyTimeframe = "M5";
input int HistoryBars = 30;
input int PollIntervalSeconds = 5;
input int RequestTimeoutMs = 3000;
input bool EnableOrderExecution = false;

CTrade trade;

int OnInit()
{
   EventSetTimer(PollIntervalSeconds);
   Print("SyncLeadBridgeEA initialized. Add the service URLs to MT5 WebRequest allowlist.");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
}

void OnTick()
{
   // Trading execution remains timer-driven.
}

void OnTimer()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick))
   {
      Print("Failed to read current tick for symbol ", _Symbol);
      return;
   }

   string payload = BuildDecisionPayload(tick);
   string response = "";
   int status = PostJson(StrategyServiceUrl, payload, response);

   PrintFormat("Decision poll status=%d response=%s", status, response);

   if(status == 200 && EnableOrderExecution)
      TryExecuteDecision(response);
}

string BuildDecisionPayload(const MqlTick &tick)
{
   MqlRates rates[];
   string request_id = StringFormat("%s-%u", _Symbol, GetTickCount());
   string timestamp_utc = TimeToString(TimeGMT(), TIME_DATE|TIME_SECONDS);
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

   if(tick_size > 0.0)
      value_per_point_per_lot = tick_value * (_Point / tick_size);

   if(copied <= 0)
      Print("Failed to copy rates for setup detection");

   string json =
      "{"
      "\"request_id\":\"" + request_id + "\","
      "\"timestamp_utc\":\"" + timestamp_utc + "Z\","
      "\"symbol\":\"" + _Symbol + "\","
      "\"timeframe\":\"" + StrategyTimeframe + "\","
      "\"bid\":" + DoubleToString(tick.bid, _Digits) + ","
      "\"ask\":" + DoubleToString(tick.ask, _Digits) + ","
      "\"spread_points\":" + DoubleToString(spread_points, 2) + ","
      "\"point_size\":" + DoubleToString(_Point, _Digits) + ","
      "\"value_per_point_per_lot\":" + DoubleToString(value_per_point_per_lot, 6) + ","
      "\"candles\":" + SerializeRates(rates, copied) + ","
      "\"positions\":[],"
      "\"account\":{"
         "\"balance\":" + DoubleToString(balance, 2) + ","
         "\"equity\":" + DoubleToString(equity, 2) + ","
         "\"margin_free\":" + DoubleToString(margin_free, 2) + ","
         "\"leverage\":" + IntegerToString((int)leverage) +
      "},"
      "\"indicators\":{}"
      "}";

   return json;
}

int PostJson(const string url, const string payload, string &responseText)
{
   char requestBody[];
   char responseBody[];
   string responseHeaders = "";
   string headers = "Content-Type: application/json\r\n";

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
   string json = "[";

   for(int i = 0; i < count; i++)
   {
      if(i > 0)
         json += ",";

      json += "{"
         "\"timestamp_utc\":\"" + TimeToString(rates[i].time, TIME_DATE|TIME_SECONDS) + "Z\","
         "\"open\":" + DoubleToString(rates[i].open, _Digits) + ","
         "\"high\":" + DoubleToString(rates[i].high, _Digits) + ","
         "\"low\":" + DoubleToString(rates[i].low, _Digits) + ","
         "\"close\":" + DoubleToString(rates[i].close, _Digits) + ","
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
