# Proposal: make "a research lab first" checkable

**Question asked:** is the homepage claim *"A research lab first; the monitor is
how we show our work in public"* true?

**Short answer:** the first half yes, the second half not as written, but the fix
is smaller than I first thought. The research is real and nearly every module
rests on a genuine lab paper. It simply is not visible anywhere on the monitor,
so a reader sees Eurostat, SCB and the Stanford AI Index doing the work.

## 1. What the audit found

Ten figure footers on the monitor page:

| what the figure cites | figures |
|---|---|
| DAIOE, the lab's own measure | 3 |
| JobTech job-ads pipeline, lab-built | 2 |
| Akavia partner panel, our processing | 2 |
| Eurostat, SCB, Stanford AI Index | 3 |

Zero figures link to a lab paper. The page links to `/research/` once.

So the claim currently rests on the reader's trust rather than on anything they
can check, which is the opposite of the site's stated honesty-as-aesthetic.

## 2. But the research is there

Mapping each module to work the lab has actually published or has in review:

| module | research behind it | status |
|---|---|---|
| **Exposure** | *AI Unboxed and Jobs: A Novel Measure and Firm-Level Evidence from Three Countries* | In review; ORU WP 13/2023, IZA DP 16717, Ratio WP 370. **DAIOE is the measure from this paper.** |
| **Demand** | *Artificial Intelligence, Hiring and Employment: Job Postings Evidence from Sweden* | Published, Applied Economics Letters, DOI |
| | *Automation and the Changing Composition of Skill Demand* | In review, Labour Economics |
| **Adoption** | *Who Adopts AI? Evidence on Firms, Technologies and Workers* | ORU WP 3/2026, IZA DP 18515 |
| | *The Effects of Artificial Intelligence on Jobs: Evidence from an AI Subsidy* | In review, Economic Journal |
| **Outcomes · entry-level squeeze** | *Same Storm, Different Boats: Generative AI and the Age Gradient in Hiring* | In review; ORU WP 2/2026, PDF, one-pager |
| **Outcomes · working conditions** | *Artificial Intelligence and Worker Stress: Evidence from Germany* | Published, Digital Society 4(5) |
| **Outcomes · Akavia layer** | **nothing yet** | see §4 |

Seven of eight blocks have a real, citable paper. That is a strong position and
the site is hiding it.

## 3. Proposed wording for the claim

**Option A, recommended.**
> A research lab first. The monitor is our measurement infrastructure made
> public: the same data and measures our own research runs on.

True, distinctive, and it explains why the lab should hold the monitor rather
than a national agency. It also reframes the third-party sources correctly, as
external validity around the lab's own instruments rather than as the substance.

**Option B, bolder, only if we do §4 properly.**
> A research lab first. Every module here names the research behind it.

Strongest version, and checkable, but it commits us to the provenance lines
actually being there and staying accurate as modules change.

**Option C, closest to the current sentence.**
> A research lab first; the monitor makes our measurement public, and each module
> names the research behind it.

I would take **A** for the heading and do §4 regardless. B is tempting but a
claim that must be maintained is a liability; A stays true even if a module is
added before its paper exists.

## 4. The change that does the real work

Add one "research behind this" line per module, linking to the paper. Draft
wording:

- **Exposure:** "The exposure measure is the lab's own. DAIOE is built and
  validated in *AI Unboxed and Jobs* (ORU WP 13/2023 · IZA DP 16717)."
- **Demand:** "The job-ads evidence here underpins *Artificial Intelligence,
  Hiring and Employment: Job Postings Evidence from Sweden* (Applied Economics
  Letters, 2025)."
- **Adoption:** "Who adopts, and what happens next, are the subjects of *Who
  Adopts AI?* (ORU WP 3/2026 · IZA DP 18515) and *The Effects of AI on Jobs:
  Evidence from an AI Subsidy* (in review)."
- **Outcomes · entry-level squeeze:** link the existing phrase "an independent,
  ad-based echo of the Canaries finding" to *Same Storm, Different Boats*
  (ORU WP 2/2026), which it currently does not.
- **Outcomes · working conditions:** "Related lab research on AI and wellbeing:
  *Artificial Intelligence and Worker Stress: Evidence from Germany* (Digital
  Society, 2025)."
- **Outcomes · Akavia layer:** **no research claim.** Say plainly that this layer
  is new and that research using it is in progress. Overclaiming here would
  reintroduce exactly the problem we are fixing.

Cost: about an hour, config-driven so the lines live in YAML beside the module
rather than hard-coded in `build.py`.

## 5. Two things I need from you

1. **Which wording**, A, B or C.
2. **Does *Artificial Intelligence for Public Use* (Digital Society, accepted)
   use the Akavia panel?** The ESO 2025:2 report does. If the Digital Society
   paper does too, the Akavia layer gets a real provenance line instead of
   "in progress" and seven of eight becomes eight of eight. I did not want to
   assert it without checking with you.

## 6. What I would not do

Nothing that implies a module is a research output when it is a careful
presentation of someone else's statistics. The Eurostat and SCB and AI Index
figures should keep saying exactly what they are. The point of this change is to
show that the lab has its own instruments *as well*, not to blur the line.
