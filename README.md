[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/inichirotakaeda01/makefun-gta6-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/inichirotakaeda01/makefun-gta6-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

# GTA VI Twitch CCU forecaster — variant G (median-focused, narrow spread)

Forecasts GTA VI's launch-day Twitch viewers hour by hour (hours 2–24) from
the hour-1 print, as five quantiles per hour, for
`gta6-twitch-ccu-forecast-01`.

## Model

Log-scale quantile forecaster anchored on the hour-1 print `p1`:

- **Median:** for each hour, the median across the case's own comparables
  of `ln(viewers_h / viewers_1)` on that launch's release day. Past big
  launches share one shape — a small dip in the small hours, then a strong
  rise as the big regions unlock (US East/West hit midnight local at
  05:00Z/08:00Z), peaking in the evening. The median is refit at run time
  from the comparables inside the case file, so the final case uses its
  own 42 launches; a baked-in copy of the fitted ratios is only a fallback
  for hours with too few usable comparables.
- **Spread (variant G):** deliberately narrow and tight around the median —
  a bet that the median is accurate, so the outer quantiles need not be
  wide. Log-spread `s(h) = 0.18 + 0.008 * (h - 2)`; quantiles are
  `median * exp(z_tau * s(h))` with `z = (-1.645, -0.674, 0, 0.674, 1.645)`.

## Run

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Python 3.13 standard library only, no network, deterministic.
