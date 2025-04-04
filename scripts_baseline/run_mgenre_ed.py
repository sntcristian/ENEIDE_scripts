import requests
import re
import csv
import json
from tqdm import tqdm
import pickle
from genre.trie import Trie, MarisaTrie
from genre.fairseq_model import mGENRE
import os


with open("../DZ/v0.1/paragraphs_test.csv", "r", encoding="utf-8") as f1:
    paragraphs = csv.DictReader(f1)
    paragraphs = list(paragraphs)

with open("../DZ/v0.1/annotations_test.csv", "r", encoding="utf-8") as f2:
    all_spans = csv.DictReader(f2)
    all_spans = list(all_spans)

# data to have
with open("../../GENRE/data/lang_title2wikidataID-normalized_with_redirect.pkl", "rb") as f:
   lang_title2wikidataID = pickle.load(f)

with open("../../GENRE/data/titles_lang_all105_marisa_trie_with_redirect.pkl", "rb") as f2:
    trie = pickle.load(f2)

model = mGENRE.from_pretrained("../../GENRE/data/fairseq_model_ed").eval()

output = []

pbar = tqdm(total=len(paragraphs))
for item in paragraphs:
    text = item["text"]
    data_id = item["doc_id"]
    begin = []
    end = []
    labels = []
    sentences = []
    surface_forms = [(int(ent["start_pos"]), int(ent["end_pos"]), ent["type"]) for ent in all_spans \
                     if ent["doc_id"] == data_id]
    for ent in surface_forms:
        start_pos = ent[0]
        end_pos = ent[1]
        if start_pos >= 500:
            history_start = start_pos - 500
        else:
            history_start = 0
        if end_pos + 500 <= len(text):
            future_end = end_pos + 500
        else:
            future_end = len(text)
        label = ent[2]
        mention = text[history_start:start_pos] + "[START] " + text[start_pos:end_pos] + " [END]" + text[end_pos:future_end]
        begin.append(start_pos)
        end.append(end_pos)
        labels.append(label)
        sentences.append(mention)
    results = model.sample(
       sentences,
       prefix_allowed_tokens_fn=lambda batch_id, sent: [
           e for e in trie.get(sent.tolist()) if e < len(model.task.target_dictionary)
       ],
       text_to_id=lambda x: max(lang_title2wikidataID[tuple(reversed(x.split(" >> ")))], key=lambda y: int(y[1:])),
       marginalize=False,
    )
    
    # Example output =    [[{'id': 'Q937',
    #    'texts': ['Albert Einstein >> it','Alberto Einstein >> it',    'Einstein >> it'],
    #    'scores': tensor([-0.0808, -1.4619, -1.5765]), 'score': tensor(-0.0884)}]]
    
    candidates_list = list()
    for candidates in results:
        new_list = list()
        for candidate in candidates:
            name = candidate["text"]
            score = candidate["score"].item()
            wb_id = candidate["id"]
            new_list.append({"alias":name, "score": score, "wb_id":wb_id})
        candidates_list.append(new_list[:1])

    labels = list(zip(begin, end, labels, candidates_list))
    for start_pos, end_pos, label, candidates in labels:
       output.append(
           {
               "doc_id": item["doc_id"],
               "start_pos": start_pos,
               "end_pos": end_pos,
               "surface" :text[start_pos:end_pos],
               "type": label,
               "identifier":candidates[0]["wb_id"],
               "score":candidates[0]["score"]
           }
       )
    pbar.update(1)
pbar.close()


o_keys = output[0].keys()
if not os.path.exists("../results/DZ/mgenre_ed"):
    os.makedirs("../results/DZ/mgenre_ed")

with open('../results/DZ/mgenre_ed/output.csv', 'w', encoding='utf-8') as f:
    dict_writer = csv.DictWriter(f, o_keys)
    dict_writer.writeheader()
    dict_writer.writerows(output)

