import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from app.schemas import CandleSnapshot
from app.regime import RegimeSnapshot
from app.strategies.zigzag_v7 import context

class V7Tests(unittest.TestCase):
    def test_open_candle_cannot_change_gate(self):
        at = datetime(2026, 1, 5, 11, tzinfo=timezone.utc)
        candles = [CandleSnapshot(timestamp_utc=at-timedelta(minutes=5*(60-i)), open=200-i, high=201-i, low=199-i, close=200-i, volume=1) for i in range(60)]
        regime = RegimeSnapshot('range','both','test')
        original = context(candles, at, 'sell', SimpleNamespace(), regime)
        self.assertTrue(original[0])
        future = candles[-1].model_copy(update={'timestamp_utc':at,'close':99999})
        self.assertEqual(original, context(candles+[future],at,'sell',SimpleNamespace(),regime))

    def test_buy_veto_and_unknown_history(self):
        at = datetime(2026,1,5,11,tzinfo=timezone.utc)
        self.assertFalse(context([],at,'buy',SimpleNamespace(),RegimeSnapshot('insufficient_history','none','test'))[0])
