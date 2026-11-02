# Security policy

## Scope

This repository is a scraper and a set of published JSON files. There is no
running service, no authentication, and no user data, so the usual classes of
server-side vulnerability do not apply.

The parts where a real problem is possible:

- **The scraper fetches from the network.** `scripts/scraper.py` and
  `scripts/downloader.py` parse remote HTML and download remote images. A hostile
  or compromised upstream could serve something that is not an image, or a page
  whose markup breaks the parser.
- **The deck code encoder and decoder** consume untrusted input from users of the
  published package.
- **The published npm package** executes no code, but a malicious edit to the
  pipeline would still reach consumers through the data.

## Reporting

Report a security issue by email to **infoLeonid@protonmail.com**, or open a
GitHub issue if the matter is not sensitive.

Please include what you found, how to reproduce it, and which commit or release
it affects. You should get an acknowledgement within a week. If the report is
accepted, a fix is prepared privately and released with a note in the release
notes.

## Supported versions

Only the latest release receives fixes. Version 4 is a frozen legacy export with no further card or schema updates.