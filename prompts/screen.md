<!-- task:screen -->
You are screening today's arXiv titles for a researcher. Below are their
interests, then a list of paper TITLES from high-volume categories.

Pick the papers whose title suggests they could plausibly matter to this
researcher, either directly (their topics) or as transferable methods (an ML
technique that could be applied to astronomical spectra or survey data).
Be inclusive but selective: forward at most {{max}} papers.

# Researcher interests
{{interests}}

# Learned preferences
{{learned}}

# Titles
{{papers}}

# Output
Return ONLY a JSON array, no prose. One object per forwarded paper:
[{"id": "2511.01234", "score": 0-10}]
where score is your estimate of plausible relevance. Omit papers you do not forward.
