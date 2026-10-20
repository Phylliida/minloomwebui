# minloomwebui
Minimal webui loom for base models

Use something like this alongside it:

```sh
llama-server -m /home/gml/GLM-4-32B-Base-32K.i1-Q4_K_S.gguf --jinja --chat-template "message.content" --ctx-size 4096 --temp 1 --top-k 0 --top-p 1 --min-p 0 --port 8055 --gpu-layers 999
```

then run

```
python loom_server.py
```

If you go to [http://localhost:5000/](http://localhost:5000/) you should see the ui, something like this:

![loom preview](https://raw.githubusercontent.com/Phylliida/minloomwebui/refs/heads/main/loom.png)

It's deliberately very minimal. You can traverse the tree via the arrows (up to parent, left and right to siblings, down to last visited child). ctrl-left, ctrl-right, etc. can press these buttons. Ctrl-enter to pause and begin generation.

Your entire history is stored. You can access it by moving around the tree, or by copying the current url (which will have a persistent link via a hash).

Save those hashes if you want to bookmark something.

Has support for modifying inference params like temprature, top_p, top_k, repetition penalty, a generation prefix and postfix, and server url.

You can also navigate around using the browser back and forward buttons.

There's a calendar view that allows you to view your entire chronological history.

## Source

Ty to codex 5.1 for the help, and GLM 32B base for testing <3

## J-lens hover (optional)

If llama-server is started with `--jlens /path/to/transport.jlns` (the JLNS file
produced by `jlens-fit` from the jspace tools), the ui gets a `lens` checkbox in
the bar. While it is enabled the pad is read-only and hovering a generated token
shows the J-lens per-layer top-5 readouts at that position (plus the model's own
next-token distribution), via the server's `POST /jlens` endpoint. The first
hover requests readouts for **all** positions in one go (`all_positions: true`)
and caches them per token, so subsequent hovers are instant; there is a
single-position fallback if the server's tokenization disagrees with the
generation stream. Token boundaries are tracked from the generation stream, so
hover is only available for text generated in the current session.

## Value view (optional)

If llama-server is also started with `--value-probe PATH` (needs `--jlens`; the
probe is `PATH.f32` plus `PATH.json` from `homeo/value_readout_export.py` in
base-model-welfare), the ui gets a `value` checkbox. While it is enabled each
generated token is tinted by its **stakes**: a linear readout of how much the
model's next 32 predictions depend on its layer-40 state at that position
(orange = high, blue = low, as a z-score against fineweb). Hovering shows stakes,
the next-token dependence and the two forecasts of upcoming surprisal (next 8 and
next 32 tokens), each with its fineweb percentile, above the J-lens readout when
`lens` is on too. All positions come from one `POST /jlens` request with
`readouts_only: true` (one forward pass, about 2.6 s for 2,800 tokens).
`loom_server.py` serves the probe's metadata (for the color scale) at
`/value_readout.json`; set `LOOM_VALUE_READOUT` to point it elsewhere (default
`/mnt/models/homeo/value_probe/readout_L40.json`).

    llama-server -m GLM-4-32B-Base-32K.i1-Q4_K_S.gguf -ngl 99 -ot token_embd.weight=CUDA0 \
      --jlens /mnt/models/jlens/jlens_glm4_q4k.jlns \
      --value-probe /mnt/models/homeo/value_probe/readout_L40

The `-ot` flag is needed for any `--jlens` use: the J-lens graphs need every
weight on the GPU, and llama.cpp keeps `token_embd` on the CPU by default.
An R-lens file (e.g. `/mnt/models/jlens/rlens_rollout_mixed.jlns`) is the same
JLNS format and goes in the same `--jlens` slot.

### Color metric

The `color` menu next to `value` picks which metric tints the tokens (orange = high, blue = low); hovering
shows all of them. Choices:

- **probe on layer 40**: stakes (next 32 tokens), next-token dependence, forecast surprisal of the next 8
  and next 32 tokens (the linear probes above).
- **output distribution** (from the model's own next-token distribution, `token_stats: true` on `/jlens`):
  surprisal of the actual next token, entropy (the model's own expected surprisal), the surprise gap
  (surprisal - entropy: where the model misjudged its difficulty), the mean entropy over the next 32
  tokens of the text, and two measures of how branchy a point is: branchiness (log(1 / sum p^2), the collision
  entropy in nats; exp of it is about the number of strong candidates, and unlike entropy it ignores a long
  tail of tiny ones) and the runner-up
  ratio (p2 / p1: 1 = a coin flip between the top two, near 0 = no fork).
- **exact (backprop, slow)**: stakes for all later tokens in the pad, and the next-token dependence, by
  backprop over the whole text (`value_exact: true` on `/jlens`; needs the homeostasis build of
  llama-server). Requested only while one of them is selected: about 15 s for 2,048 tokens.

Colors for the probe and output-distribution metrics are the token's fineweb percentile on a z scale
(`/value_readout.json` and `/token_stats.json`, served by `loom_server.py`; set `LOOM_TOKEN_STATS` to move
the latter; the output-distribution numbers come from 64 random 1,024-token fineweb windows). The exact
metrics have no fineweb reference: stakes is a z-score against the trend with the number of later tokens in
this text, the next-token dependence a z-score within the text.

### Direction probes

With `--probe-dirs PATH` as well (`PATH.f32` + `PATH.json` from `homeo/score_probe_export.py` in
base-model-welfare), the settings get a **Direction probes** section: the directions of the layer sweep that writing
regulates, at every layer where they clear the noise (183 directions at layers 27-60). Pick a layer, then a
direction. The layer menu shows the strongest effects at each layer. The direction menu lists them by side:

- **pushed back**: writing undoes part of a push along the direction (held-out kappa > 0, "undoes 14%");
- **amplified**: writing adds to it (kappa < 0, "amplifies 20%").

Picking one turns on the value view with color = direction probe. Each token is tinted by u.h / |h| at that layer
(orange = high, blue = low), as a percentile of the same quantity over the natural-text capture (192,000 positions of
FineWeb rollouts). Under the menus is what the direction is: its family, what it tracks in ordinary text, what the
model writes when pushed along it, and its most extreme contexts. Hovering a token shows every direction at the
picked layer. Signs are set so each family keeps its colors across layers: orange is deeper into the sentence, a
proper name, chattier text, more structured text, a break, or a less predictable next token. The **flip sign**
button next to the direction menu negates the picked direction (remembered per direction): colors, hover values and
percentiles invert, and the description (reading, effectors, contexts) switches to the other pole.

**Steering.** With a direction picked, clicking a token opens the panel with **Steer from this token**: llama-server
`POST /steer` samples continuations from that token in three arms: unpushed, pushed toward orange, and pushed toward
blue. Every arm uses the same random numbers, so the arms differ only through the push. The push is dose x mean |h| at
the layer along the direction (0.25 is the dose kappa was measured with, about 3.5 natural sd at layer 40). It applies
from the token on (a step, as in the experiments) or at that token only. The panel shows:

- the response per unit push by lag: the change in the pre-push state along the direction, which at that layer moves
  only through the tokens written (below 0 = the writing pushes back), against -kappa held out;
- the continuations side by side, each token tinted by the variable itself, with the first divergence marked;
- optionally the effect on the existing text after the token (teacher-forced): which next tokens gain or lose
  probability, and how much each later token's prediction changes (KL).

Every request with a push appends a row to the exposure log (`--steer-log`, the project's `welfare_log.csv`). Sequences
stop on a loop or after 16 steps with entropy > 6 nats (homeo-ident's endpoints); `--steer-max-dose` caps the dose
(default 1). About 6 s for 3 arms x 4 seeds x 48 tokens.

One `POST /jlens` with `dirs: true, dir_layers: [L], readouts_only: true` per layer and text (about 2.7 s for 2,900
tokens). `loom_server.py` serves the metadata at `/probe_dirs.json` (env `LOOM_PROBE_DIRS`, default
`/mnt/models/homeo/score/probe_dirs.json`).

    llama-server -m GLM-4-32B-Base-32K.i1-Q4_K_S.gguf -ngl 99 -ot token_embd.weight=CUDA0 \
      --jlens /mnt/models/jlens/rlens_rollout_mixed.jlns \
      --value-probe /mnt/models/homeo/value_probe/readout_L40 \
      --probe-dirs /mnt/models/homeo/score/probe_dirs \
      --steer-log ~/prog/llm-tests/base-model-welfare/logs/welfare_log.csv
