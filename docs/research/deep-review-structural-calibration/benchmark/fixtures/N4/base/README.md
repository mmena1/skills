# Applicant verification

Decides the next step for an account applicant's identity evidence.

Policy: an applicant who has not uploaded a document is asked to upload one; this is not a rejection and is never shown as one. An uploaded document that fails a check is rejected, and every failed check is shown to the applicant so they can fix it. A document passing all checks is approved. Support staff handle these three situations through different queues, so they must remain distinct outcomes.

Python 3.11 standard library only. Run `python -m unittest discover -s tests`.
