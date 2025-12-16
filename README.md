# minloomwebui
Minimal webui loom for base models

All history is saved in one big .jsonl file, just copy your browser url for current state to save it.

Use something like this alongside it:

```sh
llama-server -m /home/gml/GLM-4-32B-Base-32K.i1-Q4_K_S.gguf --jinja --chat-template "message.content" --ctx-size 4096 --temp 1 --top-k 0 --top-p 1 --min-p 0 --port 8055 --gpu-layers 999
```

then run

```
python loom_server.py
```

If you go to [http://localhost:5000/](http://localhost:5000/) you should see the ui, something like this:

![loom preview](raw.githubusercontent.com/Phylliida/minloomwebui/refs/heads/main/loom.png)

It's deliberately very minimal. There's an undo but no support for viewing a tree, just you and the text box.

However your entire history is stored. You can access it by moving prev and next (or typing in an index), or by copying the current url (which will have a persistent link via a hash).

Save those hashes if you want to "bookmark" something.

You can also navigate around using the browser back and forward buttons.

There's a calendar view at [http://localhost:5000/calendar](http://localhost:5000/calendar) that allows you to view your entire chronological history.

## Source

Ty to codex 5.1 for the help, and GLM 32B base for testing <3