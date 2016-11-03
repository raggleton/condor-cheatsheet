#condor-cheatsheet

Generate a page of HTCondor commands, and their brief descriptions.

NB to run locally, because we load a local file, Chrome requires this to be done on a "server".
The easiest way to do this is to start a local HTTP server:

```
python -m SimpleHTTPServer
```

then go to `localhost:8000` in your browser (or whichever port it assigns)

TODO:

- cache manuals for different releases, make selectable

- add in usage, although need to stop it hogging the whole screen