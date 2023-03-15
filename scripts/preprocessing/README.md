# Preprocessing

We start with the raw document and annotation ("key") files from MUC-3 and MUC-4, which can be found in `data/raw/splits/{train,dev,test}/{keys,docs}`. To preprocess the documents, we use essentially the `proc_texts.py` script that can be found [here](https://github.com/brendano/muc4_proc/blob/master/scripts/proc_texts.py) (this script is slightly modified to accept command line arguments). To preprocess the key files, we use a lightly modified version of the `proc_keys.py` script [here](https://github.com/brendano/muc4_proc/blob/master/scripts/proc_keys.py). The main important distinction between the original version of this script and the one in this repo is that the latter outputs annotations for *all* of the original slots &mdash; not just the entity-valued ones. So in summary, to preprocess both documents and annotations, you would run the following from the project root:

```
python scripts/preprocessing/proc_texts.py data/raw/splits/{train,dev,test}/docs/ data/semiprocessed/{train,dev,test}/{train,dev,test}_docs.json 
python scripts/preprocessing/proc_docs.py data/raw/splits/{train,dev,test}/keys/ data/semiprocessed/{train,dev,test}/{train,dev,test}_keys.json
```

So the files in `data/semiprocessed/` contain the outputs from running these commands. However, for this project, I found it helpful to *combine* the annotations and the documents into single files, and to augment them with some additional information:
- Sentence splits, as computed by SpaCy's sentence splitter
- Document- and sentence-level offsets of slot-filling entities
Assuming you have completed the first preprocessing step above, to obtain these versions of the data, you can run:

```
python scripts/preprocessing/preprocess.py
```

which will write these versions to `data/processed/train/{train,dev,test}/{train,dev,test}.json`. Alongside these files, it will also write JSON files `{train,dev,test}_unlocatable_{entities,locations}.json` that identify entities and locations that, though annotated as slot fillers, cannot be found as literal strings in the document text.