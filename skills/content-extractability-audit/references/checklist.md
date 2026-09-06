# Content extractability checks

| check_id | The question | Fires when |
|---|---|---|
| `unanswerable_who` | Who is this company? | No page title, `og:site_name`, or Organization structured data anywhere in the crawl |
| `unanswerable_what` | What does it offer? | Homepage H1 text + meta description combined is <6 words |
| `unanswerable_who_for` | Who is it for? | No audience-framing phrase ("for small businesses", "built for teams", "designed for", ...) found on any key page |
| `unanswerable_where` | Where does it operate? | No address-shaped text, phone number, or structured `address` property anywhere |
| `vague_value_proposition` | Is the language concrete? | >0.8 vague marketing phrases per 100 words on a key page (curated list: "world-class", "cutting-edge", "seamless experience", ...) |
| `weak_heading_hierarchy` | Can structure be parsed? | >=30% of pages (of >=3) with >150 words have zero H1s or multiple H1s |
| `missing_contact_context` | Is there a contact channel? | No email or phone number found in visible text anywhere |

All four "who/what/who-for/where" checks are **presence** checks by design:
they ask "is there any qualifying signal at all", not "is the existing
answer good". This keeps them deterministic, generalizable to unseen sites,
and resistant to false positives — see the parent SKILL.md's Constraints.
