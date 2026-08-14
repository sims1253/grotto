# R corpus research for human theme evaluation

## Bottom line

**Evidence:** I did not find an established, human-evaluation-ready R corpus for
comparing editor themes or code readability. The established R corpora I found
were built for language/runtime or static-analysis research, not controlled
visual evaluation.

**Design judgment:** Use a small, frozen, CRAN-derived master corpus and create
matched parallel forms from it. Do not download or process all of CRAN. Keep the
source pool fixed for reproducibility, but do not show the same participant the
same excerpt under multiple themes: rotate different matched excerpts across
conditions and experiments.

VS Code is not a blocker. Its official extension API defines
`contributes.themes` as an array of entries, each with a label, UI type, and JSON
path. One extension can therefore expose all nine candidates in the Color Theme
picker before a winner is selected ([official contribution-point
documentation](https://code.visualstudio.com/api/references/contribution-points#contributes.themes)).

## Reproducible R source pools

### CRAN source packages — recommended source pool

**Evidence:** CRAN currently provides source packages, links to specific package
versions, and an archive of previous and withdrawn versions
([CRAN contributed packages](https://cran.r-project.org/web/packages/)). CRAN
policy says old package versions are archived in perpetuity
([CRAN Repository Policy](https://cran.r-project.org/web/packages/policies.html)).
R source packages have a standardized layout; ordinary R implementation files
are normally under `R/`, while examples, tests, and vignettes are separable
([Writing R Extensions: package
structure](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Package-structure)).

CRAN is a source pool, not one uniformly licensed corpus. Every package must
declare a `License` in `DESCRIPTION`, possibly with extra terms in a package
`LICENSE` file ([Writing R Extensions:
licensing](https://cran.r-project.org/doc/manuals/r-release/R-exts.html#Licensing)).

**Design judgment:** Select a few versioned tarballs, extract only chosen `.R`
files, and record package, version, canonical URL, path, excerpt line range,
SHA-256, copyright/attribution, and the package's exact license. Prefer
permissively licensed packages if excerpts will be redistributed with the
experiment. Preserve notices and attribution; do not infer that “on CRAN” means
all code has the same reuse terms.

### CRAN snapshots

**Evidence:** CRAN's archive preserves package versions, but the cited CRAN page
does not itself define a whole-repository date snapshot format. Posit Package
Manager is a first-party documented option when a date-level CRAN state is
needed: it tracks source changes as snapshots and supports `YYYY-MM-DD` aliases
([repository versioning and snapshot
identifiers](https://docs.posit.co/rspm/admin/repositories/#snapshot-identifiers)).

**Design judgment:** A 20–30-file experiment does not need a full snapshot.
Versioned package URLs plus file hashes are simpler and sufficient. A snapshot
date may be recorded as additional provenance, not as a substitute for hashes.

### R-universe — useful index, not the frozen authority

**Evidence:** R-universe continuously rebuilds packages from Git repositories
and explicitly describes itself as continuously updated
([catalogue documentation](https://docs.r-universe.dev/browse/get-started.html)).
Its API exposes package/version/license metadata, upstream commit (`RemoteSha`),
and source-archive SHA-256 (`_sha256`)
([API documentation](https://docs.r-universe.dev/browse/api.html)). It is an open
publishing system and does not apply CRAN-style vetting.

**Design judgment:** R-universe is convenient for discovery and commit/hash
provenance. Do not identify an experimental stimulus merely as “latest from
R-universe”; pin the upstream commit or archive hash and retain the package
license metadata. R-universe does not retain old package versions by default,
although its documented `/api/snapshot` export can create a fixed repository
([reproducibility documentation](https://docs.r-universe.dev/install/reproducibility.html)).

## Existing R corpora and benchmarks

### R Code Intelligence dataset (2024/2025) — possible seed, not a visual benchmark

**Evidence:** Zhao and Fard created an open R dataset for code summarization and
method-name prediction and explicitly separated Base-R and Tidyverse styles
([paper](https://arxiv.org/abs/2410.07793), [dataset
record](https://doi.org/10.5281/zenodo.13871742)). It pairs function-level code
with natural-language descriptions, so it is closer to a reusable comprehension
stimulus pool than a raw CRAN mirror. It was nevertheless constructed for
machine code-intelligence evaluation, not editor-theme or readability research.

**Design judgment:** Consider its code–description pairs when authoring objective
comprehension questions, but do not adopt it wholesale or assume the aggregate
dataset license supersedes the licenses of code copied from upstream projects.
Retain original source and license provenance for every redistributed excerpt.

### 2024 real-world R code corpus

**Evidence:** Sihler et al. analyzed 4,230 publication-associated R scripts and
358,989 files from all 19,450 CRAN packages available on 2023-05-05. They report
that package and research-script code differ, and identify common features such
as assignments, function calls, name-based indexing, `if`, and loops
([paper: sources and
method](https://arxiv.org/html/2401.16228#S3.SS1.SSS2)). The paper provides a
reproducibility package, but the Zenodo record is a single 4.4 GB archive
([artifact record](https://zenodo.org/records/10569379)). The artifact record is
CC BY 4.0; embedded upstream package files should still be checked against their
own package licenses before redistribution.

**Design judgment:** This is the best current evidence for *stratifying* a small
sample of realistic R syntax, but it is far too large and not designed as a
human readability corpus. Use the paper's feature categories; do not download
the 4.4 GB artifact for this project.

### Purdue R Corpus / Shootout tasks (2012)

**Evidence:** Morandat et al. assembled 3.9 million R lines: 515 Bioconductor
packages, 1,238 CRAN packages, base R, miscellaneous code, and 11 R
implementations of Computer Language Benchmarks Game tasks. It ran on R 2.12.1
and was built to study language design and runtime behavior
([paper, section 5.2](https://janvitek.org/pubs/ecoop12.pdf#page=15)). The authors
had to implement the Shootout tasks in R because R versions were not then
available.

**Design judgment:** This is important precedent for an R benchmark corpus, but
it is old, performance-oriented, and not a standardized visual-readability task
set. Algorithmic benchmark programs also underrepresent ordinary data-analysis
and package code. Do not adopt it as the human-evaluation corpus.

## Same code versus parallel forms

### What the design literature establishes

Within-subject experiments can confound condition, presentation order, and
stimulus identity. Lewis gives a paired-Latin-square method that simultaneously
balances immediate sequential effects and condition–stimulus pairing
([primary paper](https://doi.org/10.1177/154193128903301812)). Bradley gives a
Latin-square construction for counterbalancing immediate sequential effects
([primary paper](https://doi.org/10.1080/01621459.1958.10501456)). These methods
support counterbalancing; they do not prove that two code excerpts are equally
difficult.

### Implications for this evaluation — design judgment

- Repeating an identical excerpt under every theme controls content exactly,
  but comprehension, search, and error-finding become easier after the first
  exposure. Theme is then entangled with memory, strategy learning, and order.
- Completely unrelated code on every condition avoids direct repetition but
  can replace familiarity bias with code-difficulty bias.
- The practical compromise is matched parallel forms: distinct excerpts
  matched on observable features, with theme–excerpt and theme–position pairings
  rotated across blocks or participants.
- A single participant cannot both see every excerpt only once and provide a
  fully crossed estimate for every theme × excerpt combination. Treat this as a
  structured personal comparison, use several excerpts per theme, and preserve
  item-level results rather than claiming a population effect.
- Keep a stable, hidden master corpus across project versions for auditability.
  For a returning participant, draw an unused parallel form for the next
  experiment. Changing the source population itself on every version would make
  results less comparable; changing the *assigned excerpts* is enough.

## Concrete minimal recommendation

1. Package the nine candidate `family × Day/Evening/Night` themes in one local
   VS Code extension, with neutral/coded labels during collection.
2. Curate **27 excerpts** (three disjoint forms of nine), approximately 25–60
   visible lines each, from a small set of pinned CRAN package versions. This is
   a tiny text corpus, not a memory-intensive analysis job.
3. Sample ordinary `R/` implementation code and deliberately cover the common
   constructs reported by Sihler et al.: function definitions/calls,
   assignments, indexing, conditionals, loops, strings, comments, numbers, and
   nested delimiters. Exclude generated files, giant literal tables, deliberate
   parser-error tests, and excerpts needing secret or personal data.
4. Match excerpts before testing on line count, nonblank lines, nesting depth,
   token-class counts, comment proportion, number of identifiers, and broad task
   type. Pilot the comprehension/search questions once and revise grossly
   unequal items before collecting preference data.
5. In each block, show each theme with a different excerpt. Across three blocks,
   give each theme one excerpt from each matched form and rotate theme order and
   excerpt assignment. With multiple participants, use counterbalanced lists so
   every excerpt is paired with every theme equally often; with one participant,
   record the unavoidable item confound.
6. Never show a participant the same excerpt twice for timed comprehension,
   search, or seeded-error tasks. An identical frozen diagnostic/UI specimen is
   still reasonable for a brief visual-state inspection, but analyze that as a
   visual check rather than an independent repeated performance task.
7. Store a corpus manifest with source URLs, versions, hashes, paths/ranges,
   licenses, matching metrics, task answers, assignment seed/list, and prior
   exposure. Freeze it before looking at preferences.

This design keeps the evaluation reproducible, avoids the 4.4 GB corpus and any
bulk CRAN processing, reduces familiarity bias, and still lets content and order
be audited separately from theme preference.
