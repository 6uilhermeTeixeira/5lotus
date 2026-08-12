#property strict
#property script_show_inputs
#property version "1.00"
#property description "Exports broker tick history to the 2Lotus spool. It never trades."

input string CollectorId = "2lotus-history-01";
input string CaptureSymbol = "XAUUSD";
input int LookbackDays = 30;
input int ChunkMinutes = 60;

string outputDirectory;
int digits;
double pointSize;
ulong sequence = 0;
long exportedTicks = 0;
int chunksWithData = 0;
int emptyChunks = 0;
int failedChunks = 0;

void OnStart()
  {
   if(LookbackDays < 1 || ChunkMinutes < 1 || ChunkMinutes > 1440)
     {
      Print("Invalid parameters: LookbackDays >= 1 and ChunkMinutes between 1 and 1440 are required.");
      return;
     }
   if(!SymbolSelect(CaptureSymbol, true))
     {
      PrintFormat("Cannot select symbol %s: error=%d", CaptureSymbol, GetLastError());
      return;
     }

   digits = (int)SymbolInfoInteger(CaptureSymbol, SYMBOL_DIGITS);
   pointSize = SymbolInfoDouble(CaptureSymbol, SYMBOL_POINT);
   outputDirectory = "2lotus-ticks\\" + CollectorId;
   FolderCreate(outputDirectory, FILE_COMMON);

   datetime serverNow = TimeTradeServer();
   if(serverNow <= 0)
      serverNow = TimeCurrent();
   ulong endMsc = (ulong)serverNow * 1000;
   ulong startMsc = endMsc - (ulong)LookbackDays * 86400000;
   ulong chunkMsc = (ulong)ChunkMinutes * 60000;

   PrintFormat("2Lotus history export started: symbol=%s from_msc=%I64u to_msc=%I64u chunk_minutes=%d",
               CaptureSymbol, startMsc, endMsc, ChunkMinutes);

   for(ulong fromMsc = startMsc; fromMsc < endMsc; fromMsc += chunkMsc)
     {
      ulong candidate = fromMsc + chunkMsc - 1;
      ulong toMsc = candidate < endMsc ? candidate : endMsc;
      ExportChunk(fromMsc, toMsc);
     }

   WriteManifest(startMsc, endMsc);
   PrintFormat("2Lotus history export finished: ticks=%I64d data_chunks=%d empty_chunks=%d failed_chunks=%d directory=%s",
               exportedTicks, chunksWithData, emptyChunks, failedChunks, outputDirectory);
  }

void ExportChunk(const ulong fromMsc, const ulong toMsc)
  {
   MqlTick ticks[];
   ResetLastError();
   int count = CopyTicksRange(CaptureSymbol, ticks, COPY_TICKS_ALL, fromMsc, toMsc);
   if(count < 0)
     {
      failedChunks++;
      PrintFormat("CopyTicksRange failed: from=%I64u to=%I64u error=%d", fromMsc, toMsc, GetLastError());
      return;
     }
   if(count == 0)
     {
      emptyChunks++;
      return;
     }

   string fileName = outputDirectory + "\\" + CaptureSymbol + "-history-" +
                     IntegerToString((long)fromMsc) + "-" + IntegerToString((long)toMsc) + ".part.csv";
   int handle = FileOpen(fileName, FILE_WRITE|FILE_CSV|FILE_ANSI|FILE_COMMON, ',');
   if(handle == INVALID_HANDLE)
     {
      failedChunks++;
      PrintFormat("Cannot open history spool %s: error=%d", fileName, GetLastError());
      return;
     }

   FileWrite(handle, "time_msc", "sequence", "bid", "ask", "last", "volume", "volume_real", "flags", "point_size");
   for(int index = 0; index < count; index++)
     {
      FileWrite(handle,
                IntegerToString(ticks[index].time_msc),
                IntegerToString((long)sequence++),
                DoubleToString(ticks[index].bid, digits),
                DoubleToString(ticks[index].ask, digits),
                DoubleToString(ticks[index].last, digits),
                IntegerToString((long)ticks[index].volume),
                DoubleToString(ticks[index].volume_real, 8),
                IntegerToString((int)ticks[index].flags),
                DoubleToString(pointSize, 10));
     }
   FileFlush(handle);
   FileClose(handle);

   string readyName = fileName;
   StringReplace(readyName, ".part.csv", ".ready.csv");
   if(!FileMove(fileName, FILE_COMMON, readyName, FILE_COMMON|FILE_REWRITE))
     {
      failedChunks++;
      PrintFormat("Cannot finalize history spool %s: error=%d", fileName, GetLastError());
      return;
     }
   exportedTicks += count;
   chunksWithData++;
  }

void WriteManifest(const ulong fromMsc, const ulong toMsc)
  {
   string fileName = outputDirectory + "\\history-export-summary.txt";
   int handle = FileOpen(fileName, FILE_WRITE|FILE_TXT|FILE_ANSI|FILE_COMMON);
   if(handle == INVALID_HANDLE)
      return;
   FileWriteString(handle, "symbol=" + CaptureSymbol + "\r\n");
   FileWriteString(handle, "from_msc=" + IntegerToString((long)fromMsc) + "\r\n");
   FileWriteString(handle, "to_msc=" + IntegerToString((long)toMsc) + "\r\n");
   FileWriteString(handle, "ticks=" + IntegerToString(exportedTicks) + "\r\n");
   FileWriteString(handle, "data_chunks=" + IntegerToString(chunksWithData) + "\r\n");
   FileWriteString(handle, "empty_chunks=" + IntegerToString(emptyChunks) + "\r\n");
   FileWriteString(handle, "failed_chunks=" + IntegerToString(failedChunks) + "\r\n");
   FileClose(handle);
  }
