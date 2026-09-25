# Private sales corpus (Step 1 companion model)

Owner-deposited sources only. Files in this directory are gitignored except
this README and `incoming/.gitkeep`.

## Drop books here

Put purchased PDFs, licensed EPUBs/FB2, and other closed-access copies **you
legally own** in `incoming/`. Then from the repo root:

```bash
python scripts/ingest_sales_corpus.py
```

Owner guide (Russian): `docs/sales-knowledge/how-to-deposit-books-ru.md`

Do not ask an agent to download paywalled or pirated copies.

Openly licensed articles may be listed in the manifest by URL without being
copied here.

Nothing in this folder is an approved knowledge card or a production
playbook. Ingest never starts a training job.

## Deposited 2026-09-07 (owner)

- `sales_training_project.zip` — synthetic Q&A pack (161 pairs), not book PDFs.
- `sales_training_project.README.md` — pack README from the owner.

Tracked working copy (extracted project folder + the same zip/README):
`evals/companion_step1/`. That copy is what can enter git. This private
copy stays local. **Do not fine-tune the companion on that zip as positive
SFT** (Feel-Felt-Found is taught as a correct answer; spec 0.4 forbids it).
