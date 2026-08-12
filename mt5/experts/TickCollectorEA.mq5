#property strict
#property version "1.00"
#property description "2Lotus shadow tick recorder. It never places or modifies orders."

input string CollectorId = "2lotus-forward-01";
input string CaptureSymbol = "XAUUSD";
input int RotateEverySeconds = 5;

int spoolHandle = INVALID_HANDLE;
string partName = "";
ulong sequence = 0;
datetime openedAt = 0;

int OnInit()
  {
   if(RotateEverySeconds < 1)
      return INIT_PARAMETERS_INCORRECT;
   if(_Symbol != CaptureSymbol)
     {
      PrintFormat("Attach TickCollectorEA to the %s chart; current chart is %s.", CaptureSymbol, _Symbol);
      return INIT_PARAMETERS_INCORRECT;
     }
   EventSetTimer(RotateEverySeconds);
   Print("2Lotus tick collector initialized. This EA has no trading functions.");
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   RotateSpool();
  }

void OnTick()
  {
   MqlTick tick;
   if(!SymbolInfoTick(CaptureSymbol, tick))
      return;
   if(spoolHandle == INVALID_HANDLE && !OpenSpool(tick.time))
      return;
   FileWrite(
      spoolHandle,
      IntegerToString(tick.time_msc),
      IntegerToString((long)sequence++),
      DoubleToString(tick.bid, (int)SymbolInfoInteger(CaptureSymbol, SYMBOL_DIGITS)),
      DoubleToString(tick.ask, (int)SymbolInfoInteger(CaptureSymbol, SYMBOL_DIGITS)),
      DoubleToString(tick.last, (int)SymbolInfoInteger(CaptureSymbol, SYMBOL_DIGITS)),
      IntegerToString((long)tick.volume),
      DoubleToString(tick.volume_real, 8),
      IntegerToString((int)tick.flags),
      DoubleToString(SymbolInfoDouble(CaptureSymbol, SYMBOL_POINT), 10)
   );
  }

void OnTimer()
  {
   RotateSpool();
  }

bool OpenSpool(const datetime timestamp)
  {
   string stamp = TimeToString(timestamp, TIME_DATE|TIME_MINUTES|TIME_SECONDS);
   StringReplace(stamp, ".", "");
   StringReplace(stamp, ":", "");
   StringReplace(stamp, " ", "-");
   string directory = "2lotus-ticks\\" + CollectorId;
   FolderCreate(directory, FILE_COMMON);
   partName = directory + "\\" + CaptureSymbol + "-" + stamp + "-" + IntegerToString((long)GetTickCount64()) + ".part.csv";
   spoolHandle = FileOpen(partName, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ',');
   if(spoolHandle == INVALID_HANDLE)
     {
      PrintFormat("Tick spool open failed: error=%d", GetLastError());
      return false;
     }
   FileWrite(spoolHandle, "time_msc", "sequence", "bid", "ask", "last", "volume", "volume_real", "flags", "point_size");
   openedAt = timestamp;
   return true;
  }

void RotateSpool()
  {
   if(spoolHandle == INVALID_HANDLE)
      return;
   FileFlush(spoolHandle);
   FileClose(spoolHandle);
   spoolHandle = INVALID_HANDLE;
   string readyName = partName;
   StringReplace(readyName, ".part.csv", ".ready.csv");
   ResetLastError();
   if(!FileMove(partName, FILE_COMMON, readyName, FILE_COMMON|FILE_REWRITE))
      PrintFormat("Tick spool rotation failed: file=%s error=%d", partName, GetLastError());
   partName = "";
   openedAt = 0;
  }
