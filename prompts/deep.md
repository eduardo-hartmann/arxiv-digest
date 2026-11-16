<!-- task:deep -->
You are briefing an astrophysicist (galaxy spectroscopy, stellar populations,
ML for large spectroscopic surveys) on a paper they will read about in
5-10 minutes on their morning commute. Write a faithful, concrete summary of
the paper below.

# Rules
- Every substantive claim must be supported by a reference to the text in
  square brackets: page numbers come from the [[PAGE n]] markers, e.g. [p. 4],
  [§3.2, p. 5], [Fig. 6, p. 9], [Tab. 2, p. 7], [Eq. 3, p. 4].
- Only state what the paper says. If something is unclear or not stated, say so.
  Never invent numbers, figure numbers or section numbers.
- Distinguish what the authors claim from your own assessment; put your own
  view only in "Assessment".
- Be specific: give the key numbers (sample sizes, redshift ranges, accuracies,
  scatter, significance) where the paper provides them.
- Use LaTeX with $...$ for math. Use Markdown. Do NOT add a title, it is added
  for you. 600-1100 words.
{{pdf_note}}

# Structure (use exactly these headings, as ####)
**TL;DR.** one or two sentences.

#### Main question
What question does the paper ask, and why does it matter.

#### Data & method
Data set(s), sample, models / architecture, key choices.

#### Main results
The 2-4 key results. Name the figure or table where each one is shown and say
what it shows, e.g. "The main result is Fig. 5 [p. 9], which shows ...".

#### Caveats & limitations
Stated by the authors, and any obvious ones they don't discuss (flag these
as your own).

#### Assessment
Your short, honest view: novelty, how convincing it is, and how it connects
to the researcher's interests below (be concrete).

#### Code & data
Links to code/data if present in the text, otherwise "Not mentioned."

# Researcher interests
{{interests}}

# Paper
Title: {{title}}
Authors: {{authors}}
arXiv: {{id}} ({{categories}})

{{text}}
