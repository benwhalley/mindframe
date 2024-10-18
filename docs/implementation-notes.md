# Implementation notes

## Validation rules for markdown/yaml files describing interventions

- all files in an intervention have a unique `title`

- all note templates includes at least one `[[NOTE]]` tag which is the completion that is saved as the note. If multiple `[[NOTE]]` tags are includes, multiple notes are saved in the database.

- all `judgements` define a `return`  value in the yaml frontmatter (this is done in a serialised form of a pydantic model, which specifies the schema for the return value).
 
- as a preflight check, it might be worth parsing and trying to render all templates with an empty context? This would catch any syntax errors in the templates, and also any missing/broken tags or other issues.

