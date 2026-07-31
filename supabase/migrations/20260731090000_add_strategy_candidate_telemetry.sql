alter table public.strategy_signals
  add column if not exists candle_timestamp_utc timestamptz,
  add column if not exists last_evaluated_at_utc timestamptz,
  add column if not exists suggested_action text,
  add column if not exists setup_type text,
  add column if not exists flow_status text,
  add column if not exists flow_confirmed boolean not null default false,
  add column if not exists flow_contradicted boolean not null default false,
  add column if not exists book_z numeric,
  add column if not exists tick_z numeric,
  add column if not exists flow_score numeric,
  add column if not exists spread_points numeric,
  add column if not exists updated_at timestamptz not null default timezone('utc', now());

create index if not exists strategy_signals_bot_candle_idx
  on public.strategy_signals (bot_id, candle_timestamp_utc desc);

drop trigger if exists set_strategy_signals_updated_at on public.strategy_signals;
create trigger set_strategy_signals_updated_at
before update on public.strategy_signals
for each row execute function public.set_2lotus_updated_at();

alter table public.paper_trades
  add column if not exists variant text not null default 'technical';

alter table public.paper_trades
  drop constraint if exists paper_trades_pkey;

alter table public.paper_trades
  add primary key (signal_key, variant);

alter table public.paper_trades
  drop constraint if exists paper_trades_variant_check;

alter table public.paper_trades
  add constraint paper_trades_variant_check
  check (variant in ('technical', 'flow_confirmed'));

create index if not exists paper_trades_bot_variant_status_idx
  on public.paper_trades (bot_id, variant, status, opened_at_utc desc);

alter table public.strategy_signals enable row level security;
alter table public.paper_trades enable row level security;
revoke all on table public.strategy_signals, public.paper_trades from anon, authenticated;

update public.bots
set description = 'Estratégia Fimath com MME20 e fluxo usado como veto de forte contradição.',
    strategy_description = E'- Mercado e gráfico: XAUUSD no M5.\n- Viés: fechamento e inclinação da MME20 definem compras ou vendas.\n- Gatilhos: pullback/rejeição na MME20 ou padrão fora-dentro após extensão de preço.\n- Fluxo: livro e ticks são normalizados em janela temporal; forte contradição veta a entrada, enquanto confirmação é acompanhada separadamente.\n- Telemetria: todo candidato técnico é registrado uma vez por candle com z-scores, spread e motivo da decisão.\n- Paper trades: os tracks técnico e confirmado por fluxo são medidos em paralelo, sem posições sobrepostas dentro de cada track.\n- Stop: estrutura de rejeição com buffer adaptativo de ATR(14).\n- Gestão: risco de 1%, parcial de 50% em 1R, breakeven no saldo e alvo final em 2R.\n- Validação: execução real permanece desligada até a amostra mínima e os critérios de risco serem aprovados.'
where id = 'bot-1';
