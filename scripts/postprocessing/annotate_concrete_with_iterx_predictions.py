import argparse
import json
import re

from cement.cement_document import CementDocument
from collections import defaultdict
from concrete import Argument
from concrete.util import CommunicationReader, CommunicationWriterZip
from concrete.validate import validate_communication
from os import makedirs, PathLike
from os.path import dirname
from tqdm import tqdm
from typing import *

MUC_SLOT_FILLER = List[str]
MUC_TEMPLATE = Dict[str, List[MUC_SLOT_FILLER]]


def annotate_concrete(
    concrete_input_archive: PathLike,
    concrete_output_archive: PathLike,
    model_predictions: PathLike,
    annotation_set: str,
) -> None:
    if dirname(concrete_output_archive) != "":
        makedirs(dirname(concrete_output_archive), exist_ok=True)
    writer = CommunicationWriterZip(concrete_output_archive)
    predictions_by_document: defaultdict[str, List[MUC_TEMPLATE]] = defaultdict(list)
    with open(model_predictions, "r") as f:
        for line in f:
            prediction = json.loads(line)
            doc_id = list(prediction.keys())[0]
            # each line contains all predictions for a
            # single document for templates of a single type
            templates = list(prediction.values())[0]
            predictions_by_document[doc_id] += templates

    for comm, file_name in tqdm(
        CommunicationReader(concrete_input_archive), desc="Processing..."
    ):
        cement_doc = CementDocument.from_communication(
            comm, annotation_set=annotation_set
        )
        # This dictionary construction assumes that predicted entities are singletons
        entity_mention_text_to_entity_uuid = {}
        for e in cement_doc.iterate_entities():
            assert (
                len(e.mentionList) == 1
            ), f"found non-singleton entity {e.mentionList} in communication {file_name}"
            mention_text = e.mentionList[0].text
            # We strip whitespace from the keys (i.e. mention text) due to weird
            # minor discrepancies in whitespace that can occur between the mentions
            # in JSONlines output and the mentions as given in the Concrete
            entity_mention_text_to_entity_uuid[re.sub("\s+", "", mention_text)] = e.uuid

        templates = predictions_by_document[comm.id]
        for template in templates:
            template_fillers = []
            for slot, fillers in template.items():
                if slot == "incident_type":
                    continue
                for filler in fillers:
                    assert len(filler) == 1
                    filler_text = re.sub("\s+", "", filler[0])
                    try:
                        filler_entity_id = entity_mention_text_to_entity_uuid[
                            filler_text
                        ]
                    except KeyError:
                        print(
                            f"WARNING: filler text '{filler[0]}' not found in entity mention text to entity UUID dictionary for document {file_name}"
                        )
                        continue
                    template_fillers.append(
                        Argument(role=slot, entityId=filler_entity_id)
                    )
            cement_doc.add_raw_situation(
                situation_type="EVENT_TEMPLATE",
                situation_kind=template[
                    "incident_type"
                ].upper(),  # template type is always capitalized for no particularly good reason
                arguments=template_fillers,
            )
        validate_communication(cement_doc.comm)
        writer.write(cement_doc.comm, comm.id)
    writer.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "concrete_input_archive",
        type=str,
        help="input .zip archive of Concrete Communication files; these should be communications annotated with SpanFinder predictions",
    )
    parser.add_argument(
        "concrete_output_archive",
        type=str,
        help="output .zip archive of Concrete Communication files",
    )
    parser.add_argument(
        "model_predictions",
        type=str,
        help="directory containing JSONlines-formatted model predictions",
    )
    parser.add_argument(
        "--annotation_set",
        type=str,
        default="Span Finder",
        help="the Annotation Set associated with the SpanFinder annotations in the Concrete Communication files",
    )
    args = parser.parse_args()
    annotate_concrete(
        args.concrete_input_archive,
        args.concrete_output_archive,
        args.model_predictions,
        args.annotation_set,
    )
