#!/usr/bin/env python3
# https://github.com/Aquafina-water-bottle/jp-mining-note/blob/dev/tools/hotkey.py
# Updated to be independent of JPMN

from __future__ import annotations

import re
import json
import argparse
import urllib.request
import urllib.error

from pathlib import Path
from typing import Callable, Any, Optional, Type

import pyperclip

# global constants
sentence_field = "Sentence"
sentence_audio_field = "SentenceAudio"
image_field = "Image"
frequency_field = "Frequency"
freq_sort_field = "FreqSort"
extra_field = "ExtraField"

# copied/pasted from utils to not require any weird utils dependencies

# taken from https://github.com/FooSoft/anki-connect#python
def request(action: str, **params):
    return {"action": action, "params": params, "version": 6}


def invoke(action: str, **params):
    requestJson = json.dumps(request(action, **params)).encode("utf-8")
    response = json.load(
        urllib.request.urlopen(
            urllib.request.Request("http://127.0.0.1:8765", requestJson)
        )
    )
    if len(response) != 2:
        raise Exception("response has an unexpected number of fields")
    if "error" not in response:
        raise Exception("response is missing required error field")
    if "result" not in response:
        raise Exception("response is missing required result field")
    if response["error"] is not None:
        raise Exception(response["error"])
    return response["result"]


rx_BOLD = re.compile(r"<b>(.+)</b>")



# function Anki-Browse {
#     param( $query );
#
#     Run-Json @{
#         action = 'guiBrowse';
#         version = 6;
#         params = @{
#             query = $query;
#         }
#     };
# };
def _browse_anki(query):
    invoke("guiBrowse", query=query)

def _get_sorted_list():
    # $added_notes = Run-Json @{
    #     action = 'findNotes';
    #     version = 6;
    #     params = @{
    #         query = 'added:1';
    #     }
    # };
    added_notes = invoke("findNotes", query="added:1")

    # $sorted_list = $added_notes.result | Sort-Object -Descending {[Long]$_};
    sorted_list = sorted(added_notes, reverse=True)

    return sorted_list


def _field_value(data, field_name):
    return data[0]["fields"][field_name]["value"]


def _update_field_clipboard(format_field_params: Callable[[str], dict[str, Any]], replace_newline="<br>"):
    # $clipboard = (Get-Clipboard | where{$_ -ne ''}) -join '';
    clipboard = pyperclip.paste().strip()
    clipboard = clipboard.replace("\n", replace_newline) # formatted for html

    curr_note_id = _get_sorted_list()[0]

    # $curr_note_data = Run-Json @{
    #     action = 'notesInfo';
    #     version = 6;
    #     params = @{
    #         notes = @($curr_note_id);
    #     }
    # };
    curr_note_data = invoke("notesInfo", notes=[curr_note_id])

    # $curr_note_sent = $curr_note_data.result.fields.Sentence.value;
    curr_note_sent = _field_value(curr_note_data, sentence_field)

    # $result_sent = '';
    # if ($curr_note_sent -match '<b>(?<bolded>.+)</b>') {
    #     $bolded = $matches['bolded'];
    #     # may not replace anything
    #     $result_sent = $clipboard.replace($bolded, "<b>$bolded</b>");
    # } else {
    #     # default
    #     $result_sent = $clipboard;
    # };
    result_sent = clipboard
    search_result = rx_BOLD.search(curr_note_sent)
    if search_result:
        bolded = search_result.group(1)
        result_sent = result_sent.replace(bolded, rf"<b>{bolded}</b>")

    print(f"「{curr_note_sent}」 -> 「{result_sent}」")

    # Run-Json @{
    #     action = 'updateNoteFields';
    #     version = 6;
    #     params = @{
    #         note = @{
    #             id = $curr_note_id;
    #             fields = @{
    #                 Sentence = $result_sent;
    #                 SentenceReading = '';
    #             }
    #         }
    #     }
    # };
    invoke(
        "updateNoteFields",
        note={
            "id": curr_note_id,
            # "fields": {"Sentence": result_sent, "SentenceReading": ""},
            "fields": format_field_params(result_sent),
        },
    )

    return curr_note_id


def update_sentence():
    return _update_field_clipboard(lambda x: {sentence_field: x}, replace_newline="")


def update_extra_field():
    return _update_field_clipboard(lambda x: {extra_field: x})


def _combine(src_id, dest_id, replace_fields, verbose=False):
    # Replace note fields in dest with those in src
    # Does not copy tags, does not delete src note

    src_data = invoke("notesInfo", notes=[src_id])
    dest_data = invoke("notesInfo", notes=[dest_id])
    
    note = {}
    note["id"] = dest_data[0]["noteId"]
    note["fields"] = {}
    for field in replace_fields:
        if not field in src_data[0]["fields"]:
            print(f'{field} doesnt exist in {src_data[0]["noteId"]} (src)')
            return
        if not field in dest_data[0]["fields"]:
            print(f'{field} doesnt exist in {dest_data[0]["noteId"]} (dest)')
            return
        note["fields"][field] = _field_value(src_data, field)

    invoke("updateNoteFields", note=note)

    if verbose:
        dest_data = invoke("notesInfo", notes=[dest_id])
        for field in src_data[0]["fields"]:
            src_field_value = _field_value(src_data, field)
            dest_field_value = _field_value(dest_data, field)
            if src_field_value != dest_field_value:
                if field in replace_fields:
                    print(f"{field} wasn't replaced properly!")
                if isinstance(src_field_value, str):
                    from difflib import SequenceMatcher
                    print(f'string value of field {field} differs:')
                    s = SequenceMatcher(None, src_field_value, dest_field_value)
                    i = 0 # end of previous matching block in src
                    j = 0 # " in dest
                    for block_data in s.get_matching_blocks():
                        src_start = block_data[0] # start of next matching block in src
                        dest_start = block_data[1] # " in dest
                        size = block_data.size
                        print(f'diff: src[{i}:{src_start}] = "{src_field_value[i:src_start]}" | ' 
                              f'dest[{j}:{dest_start}] = "{dest_field_value[j:dest_start]}"')
                        print(f'same: src[{src_start}:{src_start+size}] = dest[{dest_start}:{dest_start+size}] = '
                              f'"{src_field_value[src_start:src_start+size]}"')
                        i = src_start + size
                        j = dest_start + size
                    print()
                else:
                    print(f'non-string value of field {field} differs:')
                    print(f'src = {src_field_value} | dest = {dest_field_value}')
                    print()


def copy_context():
    # In practice, Picture and SentenceAudio usually change together

    curr_note_id, prev_note_id = _get_sorted_list()[0:2]
    _combine(prev_note_id, curr_note_id, [image_field, sentence_audio_field])

    # copies tags
    prev_note_data = invoke("notesInfo", notes=[prev_note_id])
    for tag in prev_note_data[0]["tags"]:
        invoke("addTags", notes=[curr_note_id], tags=tag)

    return curr_note_id


def copy_extra_field():
    curr_note_id, prev_note_id = _get_sorted_list()[0:2]
    _combine(prev_note_id, curr_note_id, [extra_field])

    return curr_note_id


def fix_sent_and_freq():
    curr_note_id, prev_note_id = _get_sorted_list()[0:2]
    prev_note_data = invoke("notesInfo", notes=[prev_note_id])
    curr_note_data = invoke("notesInfo", notes=[curr_note_id])
    prev_freq = int(_field_value(prev_note_data, freq_sort_field))
    curr_freq = int(_field_value(curr_note_data , freq_sort_field))
    print(f'prev_freq = {prev_freq}')
    print(f'curr_freq = {curr_freq}')

    if prev_freq < curr_freq:
        _combine(prev_note_id, curr_note_id, [sentence_field, frequency_field, freq_sort_field])
    else:
        _combine(prev_note_id, curr_note_id, [sentence_field])

    invoke("deleteNotes", notes=[prev_note_id])

    return curr_note_id


def browse_curr():
    id = _get_sorted_list()[0]
    invoke("guiBrowse", query=f"nid:{id}")


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--function",
        type=str,
        default=None,
        help="executes a specific function defined in this file",
    )

    parser.add_argument(
        "--enable-gui-browse",
        action="store_true",
        help="opens the newest card on run",
    )


    return parser.parse_args()


def main():
    args = get_args()

    # (comment copied from mpvacious)
    # AnkiConnect will fail to update the note if it's selected in the Anki Browser.
    # https://github.com/FooSoft/anki-connect/issues/82
    # Switch focus from the current note to avoid it.
    #
    #     self.gui_browse("nid:1") -- impossible nid (Lua)

    if args.enable_gui_browse:
        _browse_anki("nid:1")

    if args.function:
        assert args.function in globals(), f"function {args.function} does not exist"
        func = globals()[args.function]
        print(f"executing {args.function}")
        note_id = func()

        if args.enable_gui_browse:
            _browse_anki(f"nid:{note_id}")


if __name__ == "__main__":
    main()
