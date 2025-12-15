# minloomwebui
Minimal webui loom for base models

All history is saved in one big .jsonl file, just copy your browser url for current state to save it.

Use something like this alongside it:

```sh
llama-server -m /home/gml/GLM-4-32B-Base-32K.i1-Q4_K_S.gguf --jinja --chat-template "message.content" --ctx-size 4096 --temp 1 --top-k 0 --top-p 1 --min-p 0 --port 8055 --gpu-layers 999
```
