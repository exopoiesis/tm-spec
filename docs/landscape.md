# TM-Spec — Landscape & Strategic Positioning

> Date: 2026-05-10. Goal: honest assessment of where TM-Spec stands relative to
> existing declarative DFT/MD formats (AiiDA, atomate2, AiiDAlab,
> FireWorks, CWL, Snakemake, NOMAD inputs, PWmat). Used for:
> 1. Strategic decisions (avoid distracting from the first paper using TM-Spec)
> 2. Grant application context
> 3. Paper #1 introduction (positioning vs reproducibility tools)
> 4. Onboarding contributors

---

## Comparison Landscape (2026)

| Tool | Format | "Scientist without Python" | Standard? | Ephemeral compute? |
|---|---|---|---|---|
| **AiiDA** + plugins | Python WorkChain inputs (dict) | No (Python required) | **Yes, academic standard** | Difficult (daemon needs stable host) |
| **AiiDAlab** (web UI) | YAML/JSON via web form | **Yes** (web UI generates inputs) | Growing, ~ aiidalab-qe | No (requires AiiDA daemon backend) |
| **atomate2** + jobflow | Python Maker classes | No (Python + jobflow) | Materials Project ecosystem | Moderate |
| **FireWorks** | Python + YAML workflow | Partial | Was the standard (~2018), declining | No |
| **Common Workflow Language (CWL)** | YAML | Yes (but generic) | Bioinformatics standard, not DFT | Via Toil/Cromwell |
| **Snakemake** | Python-flavored DSL | Partial | Bioinformatics + reproducibility crowd | Via wrappers |
| **NOMAD's "Tools and Inputs"** | JSON/YAML upload | Yes (browser) | NOMAD ecosystem | No (submit raw inputs only) |
| **PWmat / Materials Studio** | GUI proprietary | Yes | Industry (Chinese labs) | No |
| **DFT-FE web tools** (NSF CI) | Web form | Yes | US academic, narrow | Via cluster allocations |
| **TM-Spec** (ours) | YAML + recipe registry | Yes (YAML, Recipe abstracts away Python) | Nobody (yet) | **Yes** (Lotsman + Vast.ai) |

---

## Closest Competitor — AiiDAlab QE

- URL: https://github.com/aiidalab/aiidalab-qe
- Web app on top of AiiDA + `aiida-quantumespresso`. The user fills in a form
  (structure, k-mesh, smearing, magnetic) and clicks "Run" — AiiDA launches
  PwBaseWorkChain.
- **Very good** for standard QE workflows (relax, bands, phonons).
- **Poor fit** for our use case:
  - Web app, not a git-tracked text artefact
  - AiiDA daemon required (heavy infrastructure)
  - None of our custom patches (idpp prewrap, MLIP US, sanity gates)
  - QE-only, not cross-code

Beyond AiiDAlab, **there is no direct competitor combining declarative cross-code
+ sanity gates + ephemeral compute**. This is surprising but true.

---

## 4 Niches Where TM-Spec Can Take a Position

### Niche 1 — Paper SI Format

**Nobody does this declaratively.**
- Currently, paper SI sections contain either INCAR/QE.in dumps (code-specific)
  or AiiDA Provenance archives (heavy, require AiiDA to open).
- A TM-Spec YAML file is **readable in any editor**, validates via
  `tm_spec_validator`, and requires no runtime for inspection.
- A reviewer opens one YAML file and sees structure + level of theory +
  sanity gates without installation.
- **This is a unique value proposition.**

### Niche 2 — Ephemeral Cloud Compute

- AiiDA does not work well with Vast.ai-style ephemeral instances.
- atomate2 + jobflow is more flexible, but still Python-heavy.
- TM-Spec + Lotsman = **YAML → script → ephemeral compute → updated YAML**.
  No daemon, no database.
- Niche: low-budget research, freelance scientists, students without doctoral
  cluster access.

### Niche 3 — Domain-Specific Recipes

- AiiDA workflows are generic (relax, bands, NEB) — they do not account for
  Fe-S quirks (idpp prewrap, mack PM-itinerant, V_Fe charge balance).
- TM-Spec recipes = **encyclopedia of patches** for specific chemistry.
  Each recipe encodes best practices + lessons learned (our DEADLY_MISTAKES.md
  compiled into sanity gates).
- Niche: Fe-S minerals — if it works there, it can spread to oxides, MOFs,
  perovskites via community recipes.

### Niche 4 — Educational / Reproducibility

- "I want to reproduce figure X from paper Y" — currently requires: clone AiiDA
  archive, install AiiDA, parse complex provenance. Or guess from INCAR.
- TM-Spec: one YAML file + Lotsman + cloud GPU for $5 = bit-exact reproduction.
- Niche: courses, paper-replication services, undergraduate research.

---

## Honest Assessment: Can We Become a Standard?

**No, if we compete head-to-head with AiiDA.**
- They have 10+ years of development, 100+ contributors, EU funding, integrations
  with MaterialsCloud.
- We have a single developer, no funding for a dedicated team.

**Yes, if we find a complementary niche and occupy it carefully.**
- The most promising path is **Niche 1 (Paper SI format)** + **Niche 4
  (reproducibility)**.
- If a few papers with TM-Spec SI gain traction in the community, organic
  growth becomes possible.

---

## Strategic Recommendations

1. **The first paper using TM-Spec is the test case.** If the SI with TM-Spec
   YAML passes peer review well (reviewers say "convenient, readable, understood
   the setup immediately") — that is a signal the niche is real.
2. **Do not build an AiiDA-killer.** Recipe registry is for our lab + opt-in for
   the community. Do not position TM-Spec as "better than AiiDA".
3. **Publish TM-Spec on GitHub under the MIT license.** Schema + validator +
   extractor + lint + sanity_fill = **standalone tool with no dependency on
   Lotsman**. Anyone can use it as paper SI tooling.
4. **AiiDA bridge — later.** If someone in the community requests a
   "TM-Spec → AiiDA archive converter", we will build it. Not preemptively.
5. **Possible long-term positioning:** TM-Spec becomes the **second** standard
   for **paper-grade reproducibility** (vs AiiDA for **lab-internal provenance**).
   They coexist: AiiDA for the full provenance graph during active research,
   TM-Spec for the final paper SI artefact.

---

## Precedents — How Small Declarative Formats Became Standards

- **`requirements.txt`** in Python — declarative, describes no install algorithm.
  Anyone can read it. Became a standard in ~5 years.
- **`Dockerfile`** — declarative + precisely executable. Conquered the industry
  in 5 years.
- **`schema.org` JSON-LD** — declarative metadata for the web. Became a standard
  through Google adoption.
- **`citation.cff`** for academic software — unknown at first, now natively
  supported by GitHub. Niche occupied in ~3 years.

All of these standards grew from **simple text format + tool ecosystem + early
adopters**. TM-Spec follows the same pattern:
- Simple text (YAML)
- Tool ecosystem (validator + extract + lint + sanity_fill + export_nomad)
- Early adopters (first paper submission — first publication-grade artefact)

---

## Key Risks

1. **Prescribing a scope we cannot sustain.** TM-Spec as an "AiiDA-killer" →
   failure. TM-Spec as a "narrow Fe-S DSL" → may work.
2. **Recipe registry feature creep.** Every author wants their own recipe.
   Solution: minimal core registry + community extensions via PyPI plugins.
3. **Schema versioning without a community.** As the sole user, the schema can
   evolve freely. If other labs adopt it, a compatibility layer becomes necessary.
   Solution: SemVer + freeze v1.0 after the first paper is accepted.
4. **NOMAD competing.** NOMAD has its own Metainfo schema. We leverage it via
   alignment (D-01..D-04), not competing. But if NOMAD introduces its own
   "submission template" YAML, we risk duplicating effort.
   Solution: track NOMAD development + stay compatible.

---

## What We Are Doing Now (Before the First Paper Submission)

1. ✅ TM-Spec v0.3 is ready (schema + 6 pilots + 5 tools).
2. ⏳ Submission in ~one week — paper #1 SI appendix in TM-Spec format
   as the **first publication-grade artefact**.
3. ⏳ After submission — monitoring reviewer feedback. If positive →
   publish TM-Spec on GitHub under MIT, write a blog post, post
   to Bluesky/Mastodon in the materials science community.
4. ⏳ Q-TMSPEC-9..11 (recipe registry + Lotsman runtime) — after
   submission, as a medium-term investment.

## What We Are NOT Doing Now

- ❌ AiiDA WorkChain converter — deferred until requested by the community.
- ❌ Web UI generator (TM-Spec form → submit) — deferred until the niche
   is validated as real.
- ❌ Marketing / community outreach — too early, no track record yet.
- ❌ Multi-domain spread (oxides, MOFs) — only if Fe-S submission papers
   gain traction.

---

## References

- AiiDA: https://www.aiida.net
- AiiDAlab: https://aiidalab.materialscloud.org
- atomate2: https://github.com/materialsproject/atomate2
- FireWorks: https://materialsproject.github.io/fireworks/
- CWL: https://www.commonwl.org
- Snakemake: https://snakemake.readthedocs.io
- NOMAD: https://nomad-lab.eu
- Materials Cloud Tools: https://www.materialscloud.org/work/tools
