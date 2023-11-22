import click
import json
import os

DATA_DIR = "data/semiprocessed"


@click.command()
@click.argument("output_dir")
def generate_skeletons(output_dir) -> None:
    def _has_templates(templates) -> bool:
        has_templates = bool(templates)
        return has_templates and templates[0]["message_template"] != "*"

    for split in ["train", "dev", "test"]:
        total_templates_for_split = 0
        with open(os.path.join(DATA_DIR, split, f"{split}_keys.json")) as f:
            d = json.load(f)
            new_d = {}
            for doc_id, templates in d.items():
                if not _has_templates(templates):
                    continue
                new_templates = []
                for t in templates:
                    new_templates.append(
                        {
                            "message_template": t["message_template"],
                            "incident_type": t["incident_type"],
                            "summary": "",
                        }
                    )
                    total_templates_for_split += 1
                new_d[doc_id] = new_templates
        out_path = os.path.join(output_dir, f"{split}_to_annotate.json")
        click.echo(
            f"Writing {total_templates_for_split} for {split} split to {out_path}..."
        )
        with open(out_path, "w") as f:
            json.dump(new_d, f, indent=2)


if __name__ == "__main__":
    generate_skeletons()
