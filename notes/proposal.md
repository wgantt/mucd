# Overview

This proposal presents an incremental, evidence-based approach to assembling ontology-based summaries of events described in a document. The summaries are "ontology-based" in the sense that they are intended to cover information about an event as represented by a role or slot ontology. The approach involves reading a document sentence-by-sentence and determining whether each sentence supplies any relevant information, given (1) a partial event summary (based on what has already been read) and (2) some amount of document context (i.e. previous sentences). The intention is to focus on MUC-4 as a relatively tractable case study.

# Approach

## Problem and Modeling

Given a document and a template ontology, the goal is to produce a document summary that captures all relevant information about all events of interest (w.r.t the ontology) described in the document. What counts as "relevant" information is defined by the template ontology.

The proposed approach involves reading the document sentence-by-sentence. For each sentence the model must either:
1. Decide that the sentence provides no (new) information relevant to any events already identified.
2. Generate a series of statements ("conclusions") that characterize either (a) a new event described by the sentence or (b) what roles/slots in an already-identified event are satisfied by specific entities mentioned in the sentence.
In the case of (2), the partial summary is updated by concatenating the generated statements. The result is then used as the partial summary context for the next sentence. In the case of (1), the partial summary remains unchanged. The summary is considered complete when the entire document has been read.

Apart from the current sentence, the context provided to the model consists of *at least* the partial summary written thus far, but potentially also either or both of the following:
1. Some amount of prior document context. For example, the previous *k* sentences in the document or the previous *k* **relevant** sentences.
2. Additional (context, sentence, conclusion) triples as few-shot examples.

Below, I present a fully worked through example that does not use any few-shot examples.

## Example

### Document

1. Official sources have reported that several guerilla attacks and heavy fighting took place the evening of 9 January and this morning throughout the country, and as a result, three soldiers were killed and three others injured.
2. Alleged guerilla urban commandos launched two highpower bombs against a car dealership in downtown San Salvador this morning.
3. A polic report said that the attack set the building on fire, but did not result in any casualties although economic losses are heavy.
4. During the evening of 9 January, guerrilla urban commandos bombed two electricity facilities in different places in San Salvador, which caused power outages in some areas of the capital.
5. Meanwhile, the Armed Forces Press Committee (COPREFA) reported today that three army soldiers were killed recently in clashes against members of the Farabundo Marti National Liberation Front (FMLN) in different parts of the central and eastern regions of the country.
6. The war bulletin by COPREFA stated that the clashes, in which three members of the General Juan Ramón Belloso Battalion were injured, took place in San Jose Guayabal, in the Central Cuscatalán Department, and in Santa Elena in the Easter Usulután Department.

### Templates

These are the gold-annotated templates. The numbers in parentheses next to each slot fill indicate the sentence in the document that justifies that slot fill. A "?" indicates that this information cannot technically be inferred from the text.

**Template 1**

`incident_type`: BOMBING (2)

`incident_stage_of_execution`: ACCOMPLISHED (2)

`perp_incident_category`: TERRORIST ACT (2)

`incident_date`: 10 JAN 90 (?)

`incident_location`: EL SALVADOR, SAN SALVADOR (CITY) (2)

`hum_tgt_effect_of_incident`: NO INJURY OR DEATH: - (3)

`phys_tgt_effect_of_incident`: SOME DAMAGE: CAR DEALERSHIP (2 AND 3)

`perp_individual_id`: GUERRILLA URBAN COMMANDOS (1)

`perp_organization_id`:

`phys_tgt_id`: CAR DEALERSHIP (2)

`hum_tgt_name`:

`hum_tgt_description`:

`incident_instrument_id`:  HIGHPOWER BOMBS (2)



**Template 2**

`incident_type`: BOMBING (4)

`incident_stage_of_execution`: ACCOMPLISHED (4)

`perp_incident_category`: TERRORIST ACT (4)

`incident_date`: 09 JAN 90 (4)

`incident_location`: EL SALVADOR (4), SAN SALVADOR (CITY)

`hum_tgt_effect_of_incident`:

`phys_tgt_effect_of_incident`: SOME DAMAGE: ELECTRICITY FACILITIES (4)

`perp_individual_id`: GUERRILLA URBAN COMMANDOS (4)

`perp_organization_id`:

`phys_tgt_id`: ELECTRICITY FACILITIES (4)

`hum_tgt_name`:

`hum_tgt_description`:

`incident_instrument_id`:


### Generation

Below is an example of what a gold-standard sequence of model generations might look like. Generated text is in italics. In the zero- or few-shot setting, we can imagine that the inputs are accompanied by suitable instructions in the preamble. Numbers in parentheses (e.g. "(1)") are used for brevity to indicate that the corresponding sentence from the document above should be inserted there. In this example, we imagine that the provided document context is just the previous sentence, though different strategies are obviously possible. For discussion on the format of the conclusion statements, see [Questions](#questions).

#### Turn 1

**Summary**:
**Context**:
**Sentence**: (1)
**Conclusion**: _This sentence does not present any relevant information._*

\[\*While the first sentence of the document describes a clash between military and terrorist groups, this doesn't count as a terrorist incident for MUC-4 purposes, as terrorist incidents must target civilians or civilian infrastructure. See [Questions](#questions) for more on this.\]

#### Turn 2

**Summary**:
**Context**: (1)
**Sentence**: (2)
**Conclusion**: _There was a bombing. The bombing was perpetrated by Guerilla Urban Commandos. The bombing involved two highpower bombs. The bombing targeted a car dealership. The bombing occurred in San Salvador._

#### Turn 3

**Summary**: There was a bombing. The bombing was perpetrated by Guerilla Urban Commandos. The bombing involved two highpower bombs. The bombing targeted a car dealership. The bombing occurred in San Salvador.
**Context**: (2)
**Sentence**: (3)
**Conclusion**: _The bombing did not cause any casualties.__

#### Turn 4

**Summary**: There was a bombing. The bombing was perpetrated by Guerilla Urban Commandos. The bombing involved two highpower bombs. The bombing targeted a car dealership. The bombing occurred in San Salvador. The bombing did not cause any casualties.
**Context**: (3)
**Sentence**: (4)
**Conclusion**: _There was a second bombing. The second bombing occurred the evening of 9 January. The second bombing was perpetrated by Guerrila Urban Commandos. The second bombing targeted two electricity facilities. The second bombing occurred in San Salvador._

#### Turn 5

**Summary**: There was a bombing. The bombing was perpetrated by Guerilla Urban Commandos. The bombing involved two highpower bombs. The bombing targeted a car dealership. The bombing occurred in San Salvador. The bombing did not cause any casualties. There was a second bombing. The second bombing occurred the evening of 9 January. The second bombing was perpetrated by Guerrila Urban Commandos. The second bombing targeted two electricity facilities. The second bombing occurred in San Salvador.
**Context**: (4)
**Sentence**: (5)
**Conclusion**: _This sentence does not present any relevant information._

#### Turn 6

**Summary**: There was a bombing. The bombing was perpetrated by Guerilla Urban Commandos. The bombing involved two highpower bombs. The bombing targeted a car dealership. The bombing occurred in San Salvador. The bombing did not cause any casualties. There was a second bombing. The second bombing occurred the evening of 9 January. The second bombing was perpetrated by Guerrila Urban Commandos. The second bombing targeted two electricity facilities. The second bombing occurred in San Salvador.
**Context**: (5)
**Sentence**: (6)
**Conclusion**: _This sentence does not present any relevant information._

# Evaluation

TODO: How would we evaluate model outputs?

# Annotation

Annotators are given an enumerated list of all sentences in a document and either:
1. A complete template
2. A particular slot-fill
And are asked to identify the sentence or sentences that justify each slot-fill. There are several possibilities to consider here:
- **Single-sentence justification**: In most cases, it will be possible to identify a single sentence that provides the justification.
- **Disjunctive multi-sentence justification**: Sometimes, multiple justificatory sentences can be found for a given slot-fill; in such cases, an annotator should probably mark _all_ sentences that justify the slot-fill (though in principle we could ask them to mark only the first).
- **Conjunctive multi-sentence justification**: Occasionally, some slot fills will require consulting _multiple_ sentences (I have not seen any cases where more than two are required). Annotators should mark conjunctions of sentences in these cases.
- **No available justification**: For some slots, it may not be possible to identify _any_ sentence that justifies its fillers. This could either be due to annotation errors in the original templates or due to idiosyncrasies of the ontology (e.g. the `incident_date` slot is always populated in a template, even if no evidence for it is presented in the document text itself).

# Advantages

This approach has several advantages over traditional template extraction and summarization paradigms:
- *Smaller context*: The model never has to look at the whole document at once. This both reduces space requirements and hopefully makes extraction decisions easier for the model by focusing on a single sentence at a time.
- *Evidence-based extraction*: The output allows us to associate specific extractions/slot-fills with specific sentences and claims in the text.
- *Human-readable output*: Since the output is a (very structured) summary, not a template, it's arguably more user-friendly.
- *Human-inspired*: This process of incrementally augmenting event representations as one reads seems much closer to how we actually process information as we read than traditionall template extraction and summarization methods, which look at the whole document at once.

# Disadvantages

The approach also has some drawbacks:
- *Slower runtime*: Because the model processes documents sentence-by-sentence, it will almost certainly be slower than models that work on whole documents.
- *Incomparability to template extraction systems*: The summaries output by the model do not necessarily capture distinctions between templates. In one sense, this a virtue (template distinctions can be somewhat arbitrary), but it also means that we can't directly compare our results using standard template extraction metrics.
- *Handling conjunctive multi-sentence justifications*: It will likely be impossible for the model to generate correct conclusion statements for slot fills whose justification depends on synthesizing information from multiple sentences if not all relevant sentences are accessible as document context. I suspect this is a marginal issue for MUC-4, but it's worth keeping in mind.

# Questions

There remain several questions to work out:
- **Which slots to annotate**. The slots listed in the example are probably all worth annotating. There is at least one other not listed there that I would consider adding — namely `perp_organization_confidence`, which characterizes the kind of evidence the document presents for attributing the attack to a given perpetrator (e.g. whether it's reported as fact, merely alleged, rumored, etc.).
- **Annotators**. We could plausibly do this with Turk, though I want to be sure that the annotation is high quality and there are few enough documents with templates that we could conceivably do this in-house.
- **How to handle MUC-4 idiosyncrasies**. There are two things that can disqualify an event from being marked as a terrorist incident (=annotated with a template) in MUC-4: (1) if the targets of the attack are military rather than civilian and (2) if an event is not sufficiently recent (where "recent" is defined as having occurred within two months of the writing of the article). In practice (2) doesn't seem to be much of an issue, but (1) sometimes is and it's part of what makes MUC so challenging. Certain event descriptions, such as the first sentence of the example document above, read an awful lot like terrorist incidents but are not considered to be such. Two possible ways of dealing with this are:
	- **Don't mark deceptive sentences in any special way**. If an annotator encounters a sentence that describes something that sounds like a terrorist incident but doesn't justify any of the gold annotations, the annotator just leaves it alone. We take the gold annotations at face value.
	- **Mark the deceptive sentences**. We could also ask annotators to mark any sentences that are deceptive and to indicate for each such sentence *why* it's not relevant (either because the attack has a non-civilian target or because it's an annotation error or because the event described is not sufficiently recent).
- **Gold conclusion statements**. There is a question about how to construct the "gold" conclusion statements that a model should generate. The [example above](#example) has a single ("atomic") conclusion statement for each slot justified by a given sentence. One could construct these automatically by populating templates or one could have human annotators (or a model) write more natural, fluent descriptions. It would be interesting to compare different settings here, but if I had to choose only one, I would lean toward automatically populated templates — for ease of evaluation and to facilitate faster model learning.
