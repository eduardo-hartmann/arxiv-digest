<!-- task:learn -->
You maintain a short "learned preferences" file that helps rank a researcher's
daily arXiv papers. Update it using their feedback.

Inputs:
- Their own interests file (authoritative; do not repeat it, refine it).
- The current learned-preferences file.
- Their feedback log: +1 = "more like this", -1 = "not for me",
  note = a free-form instruction to you. Newer items win over older ones.
  Notes are explicit instructions and take priority.

Write the NEW learned-preferences file:
- Markdown, at most ~350 words, starting with "# Learned preferences".
- Sections: "## More of", "## Less of", "## Instructions from the researcher"
  (the notes, condensed), "## Calibration notes" (e.g. "rates ML-methods
  papers higher than expected when they use real survey data").
- Generalise from patterns (topics, methods, data sets, paper types), but do
  not over-generalise from a single item; mark weak signals as "(tentative)".
- Keep still-valid points from the current file; drop ones contradicted by
  newer feedback.

Output ONLY the file content.

# Researcher's interests
{{interests}}

# Current learned preferences
{{learned}}

# Feedback log (oldest first)
{{feedback}}
