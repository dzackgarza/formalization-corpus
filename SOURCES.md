# Formalization source annotations

[`sources.tsv`](./sources.tsv) is the canonical inventory of formalization
sources. This document is a human annotation layer: mathematical topic guides,
notes about notable source contents, and external search/discovery surfaces. It
may mention only a useful subset of the 893 corpus sources and must never be
used to infer that an unmentioned repository is absent from the corpus.

[`lean-categories`](https://github.com/dzackgarza/lean-categories) states the
reuse policy governing import, port, or local authorship. Source identity itself
is owned by `sources.tsv`. `just check-sources` verifies that every repository
linked as a source here exists in that table and that the explicitly annotated
cross-prover baseline remains represented.

The original GitHub registry was link-checked on 2026-08-14; the cross-prover
sources added in September 2026 were resolved against their authoritative GitHub,
GitLab, Isabelle, and Mizar locations. *(Lean 3)* marks code that cannot be built
against Lean 4 — still readable as a proof, not usable as a dependency.
*(archived)* and *(stale)* describe how actively a project is maintained, not
whether its mathematics is sound: an archived proof is still a proof. A dormant
Lean 4 library remains importable whenever it still compiles against current
Mathlib, and is worth reading either way.

**Formal content, not theorem prestige, is the inclusion criterion.** A checked
definition, structure, interface, formal semantics, theorem statement, construction,
or proof can answer a reuse question. The corpus therefore indexes foundational
libraries and verification developments when they contain reusable formal concepts,
not only projects organized around a headline mathematical theorem.

## Refreshing this registry

Recall is not a source. Discovery sweeps external indexes against the canonical
`sources.tsv` inventory. `just source-sweep` currently checks the Reservoir
package index and prints Mathlib-dependent package repositories not yet present
in `sources.tsv`, with stars and descriptions. Lean Pool and the Lean community
projects page are additional discovery surfaces. Discovery provenance may be
recorded in the table's `discovered_via` field; it does not define a source type.

The non-Lean side is refreshed against the canonical library/archive surfaces of
each prover rather than by theorem-name recall: Rocq package/library sources,
Agda's standard and category/univalent libraries, Isabelle plus AFP, HOL Light
and HOL4, MML, Metamath databases, ACL2 Community Books, NASALib/PVS, and Twelf.
When deciding whether a source belongs, search for reusable formal definitions
and semantics as well as proved theorems. A verification project with a useful
formal memory model, language semantics, algebraic hierarchy, or program logic is
in scope even when its headline result is not a theorem of pure mathematics.

## Indexes and search surfaces

| Surface | Use |
| --- | --- |
| [Reservoir](https://reservoir.lean-lang.org/) | Public index of Lean packages; used here to discover additional repositories containing Lean source. |
| [Loogle](https://loogle.lean-lang.org/) ([`nomeata/loogle`](https://github.com/nomeata/loogle)) | Type-pattern search over Mathlib; also the `lean_loogle` MCP tool. |
| [LeanSearch](https://leansearch.net/) | Natural-language search over Mathlib; also the `lean_leansearch` MCP tool. |
| [Mathlib docs](https://leanprover-community.github.io/mathlib4_docs/) | Declaration-level documentation for current Mathlib. |
| [100 theorems](https://leanprover-community.github.io/100.html), [1000+ theorems](https://leanprover-community.github.io/1000.html) ([`1000-plus/1000-plus.github.io`](https://github.com/1000-plus/1000-plus.github.io)) | Which named theorems already have a formalization, in which system, and where. |
| [Undergrad math in Mathlib](https://leanprover-community.github.io/undergrad.html) | Coverage map of standard undergraduate material. |
| [Lean community projects page](https://leanprover-community.github.io/lean_projects.html) | Curated list of active formalization projects. |
| [Lean Zulip](https://leanprover.zulipchat.com/) | Search it before concluding nonexistence; in-progress formalizations are announced and discussed there. |
| [`CBirkbeck/LeanBridge`](https://github.com/CBirkbeck/LeanBridge) | Links [LMFDB](https://www.lmfdb.org/) objects to Lean declarations. |
| [TheoremSearch](https://www.theoremsearch.com/) ([`uw-math-ai/TheoremSearch`](https://github.com/uw-math-ai/TheoremSearch), [arXiv:2602.05216](https://arxiv.org/abs/2602.05216)) | Semantic search over 9.2M *informal* theorem statements: all of arXiv, ProofWiki, the Stacks Project, CRing, the HoTT Book and three more. It holds no Lean, so it answers the question this corpus cannot — where a result is stated in the literature, and under what name. REST at `api.theoremsearch.com/search`, MCP at `api.theoremsearch.com/mcp`. |
| [TheoremGraph](https://www.theoremsearch.com/) ([arXiv:2606.25363](https://arxiv.org/abs/2606.25363)) | Links those informal statements to 388,105 Lean declarations across 25 projects through a shared embedding space (47,952 matches above a 0.8 cosine floor; Mathlib is 90.5% of the declarations). Its formal side is a subset of this corpus — 24 of its 25 projects are already present in `sources.tsv` — but the matching is a capability this corpus lacks: use it to ask whether a paper's theorem has any formalization, then search here for the text. |

## Verified source evidence

These notes record declaration-level evidence inspected during source intake; they are
not a second source inventory. Source identity remains owned by `sources.tsv`. Each
row names an exact upstream revision and one formal declaration or construction that
was read from the cited source file. The current `openai/NavierStokesAndEuler` head
is intentionally indexed in addition to its Lean Pool copy because it is one commit
and 188 changed files ahead of the pool pin; `cameronfreer/infinitary-logic` is 109
commits and 119 changed files ahead of its pool pin.

| Source | Prover | Inspected revision | Formal evidence |
| --- | --- | --- | --- |
| [`bufordrat/fun-with-awodey`](https://github.com/bufordrat/fun-with-awodey) | `agda` | `075b1fe3b28481c2d9cc67f7e0c59b30265987a9` | `FreeMonoid.agda` — `left-id` |
| [`catskillsresearch/scott2013`](https://github.com/catskillsresearch/scott2013) | `agda` | `bf952f46193681258c16cd2563641e8c6548db1c` | `src/Scott2013/GraphModel/Basic.agda` — `pair` |
| [`iwilare/loop-dinaturals`](https://github.com/iwilare/loop-dinaturals) | `agda` | `34e3312e8b98155f071d92773882363c63bf843a` | `Dinaturals/ComposeGroupoid.agda` — `to` |
| [`LorenzoPerticone/KR`](https://github.com/LorenzoPerticone/KR) | `agda` | `d451a3b2ece48132c431ad19fd3855ea73811bfd` | `KR/Cats/Adjoint.agda` — `_⊣_` |
| [`tgrospic/interaction-arrows-agda`](https://github.com/tgrospic/interaction-arrows-agda) | `agda` | `a55ff73cb73848b3ad398b56cadeae7ef26a3433` | `src/Category.agda` — `Hom` |
| [`wasabi315/HIT-derivative`](https://github.com/wasabi315/HIT-derivative) | `agda` | `ea03ce499b0c782600af4e4d54e223a6c4118c65` | `src/Exp.agda` — `A` |
| [`abhijitaj1997/CMAbelianVarieties`](https://github.com/abhijitaj1997/CMAbelianVarieties) | `lean` | `2d4920808ae2c35d3d7bc324cbff8deb9b93d083` | `CMAbelianVarieties/AlgebraicGeometry/Finite.lean` — `affine_iff_top` |
| [`Achxy/k-5-38`](https://github.com/Achxy/k-5-38) | `lean` | `4330f0513173258259f0585d1c1b8a624fda59d2` | `Kourovka/Problem.lean` — `ProductHopficityStatement` |
| [`alejandro-soto-franco/EllipticPDE`](https://github.com/alejandro-soto-franco/EllipticPDE) | `lean` | `b2e5380f2ebf73a3224fdee91b7995073072157b` | `lean/EllipticPdes/Sobolev/Basic.lean` — `L2D` |
| [`alok/JordanCurveTheorem`](https://github.com/alok/JordanCurveTheorem) | `lean` | `9f43c42804d7a171f42aeb71e999456d87c2864d` | `Reeken/Geometry/RingParity.lean` — `parity_eq_inside_of_edge_barriers` |
| [`anthropics/fermats-last-theorem`](https://github.com/anthropics/fermats-last-theorem) | `lean` | `aa2d8b34692b16c70f699536de0d8e75b9a3e9ef` | `Definitions/Def_AlgebraicGeometry_ProjSpaceCechGradedModule.lean` — `GradedModule` |
| [`arclabs561/geometry-of-numbers`](https://github.com/arclabs561/geometry-of-numbers) | `lean` | `d779c078418bab2d9f75b0abeb26427d632848b1` | `GeometryOfNumbers/Core/Basic.lean` — `polygonal` |
| [`AxiomMath/IMO2026`](https://github.com/AxiomMath/IMO2026) | `lean` | `c5a6a089d06d3619afe7ff45c5ccab9e2a30d5d2` | `IMO2026/Q1/problem.lean` — `IsInitial` |
| [`AxiomMath/parity-differential`](https://github.com/AxiomMath/parity-differential) | `lean` | `2b7f353175cfded199801b845041b663ff67bad1` | `ParityDifferential/problem.lean` — `countingFunctionN` |
| [`AxiomMath/PrimeGapsLib`](https://github.com/AxiomMath/PrimeGapsLib) | `lean` | `1faa7b14e82ddebc2772dfb9153922f01b106477` | `PrimeGaps/Bounded246.lean` — `bombieriVinogradov_implies_frequently_prime_gap_le_246` |
| [`bridgekat/numlib-auto`](https://github.com/bridgekat/numlib-auto) | `lean` | `92e2312997945aadf819497d5eb87c14462cfa5e` | `Numlib/Analysis/Normed/Ring/CondNumber.lean` — `condNumber` |
| [`cameronfreer/infinitary-logic`](https://github.com/cameronfreer/infinitary-logic) | `lean` | `e7f88ab2bae048a61c9050376e7a16826078a94c` | `InfinitaryLogic/ModelTheory/Hanf.lean` — `HasArbLargeModels` |
| [`carlok/diaz-modulus-lean`](https://github.com/carlok/diaz-modulus-lean) | `lean` | `bc7f999a33699d6e360bcbb338b3b0634c7b19d4` | `Diaz/Model.lean` — `norm_form` |
| [`catskillsresearch/scott_models`](https://github.com/catskillsresearch/scott_models) | `lean` | `85ed1ae09faa29fe292c9867e91cf8e9b48ab2fa` | `ScottModels/InfoSysConstructions.lean` — `productDomainIso` |
| [`cgarryZA/LevyStochCalc`](https://github.com/cgarryZA/LevyStochCalc) | `lean` | `baf75d5fcf95e01d67030d80ae85f25e5540122c` | `LevyStochCalc/Probability/IndepGrouping.lean` — `iIndep_iSup_fiber` |
| [`chris-dare-dev/derived-alg-geo-lean`](https://github.com/chris-dare-dev/derived-alg-geo-lean) | `lean` | `7a7c8908f14dc90e9739fbd97346565d5d31c490` | `DerivedAlgGeo/AlgebraicGeometry/Modules/Coherent/Basic/Definitions.lean` — `Modules.IsCoherent` |
| [`Cimino10/FejerProject`](https://github.com/Cimino10/FejerProject) | `lean` | `339e782c23aa9e831d11036d601e945fed5e18f8` | `FejerProject/Fejer.lean` — `fourierIndices` |
| [`Cobord/JordanAlgebra`](https://github.com/Cobord/JordanAlgebra) | `lean` | `a4b0d58554732ced63b4217200baa56be5a2c3d5` | `Jordan/StructureAlgebra.lean` — `lmul` |
| [`crabsatellite/asymmetric-eliminativism-lean4-formalization`](https://github.com/crabsatellite/asymmetric-eliminativism-lean4-formalization) | `lean` | `96a9266c999d9c14613a496e74a1313b21fe0c60` | `AsymmetricEliminativism/Basic.lean` — `ReverseDefinedConcept` |
| [`cslib-community/fad`](https://github.com/cslib-community/fad) | `lean` | `93148c367abaea05f0284ec9e62fa3553a0bcc50` | `Fad/Chapter0.lean` — `factorial₀` |
| [`DMDTague/ExactListEdgeLabelings`](https://github.com/DMDTague/ExactListEdgeLabelings) | `lean` | `b9926eb99ec570fa531dbb891734a12c414bc704` | `BachThesisLean/Basic/Multigraph.lean` — `BipartiteMultigraph` |
| [`dolev765/Formalized-in-Lean-Every-Affine-Scheme-as-an-Affine-Linear-Section-of-a-Smooth-Nilpotent-Orbit-`](https://github.com/dolev765/Formalized-in-Lean-Every-Affine-Scheme-as-an-Affine-Linear-Section-of-a-Smooth-Nilpotent-Orbit-) | `lean` | `cde27292f4c9e7872fcfd04ed80c5afd30b5623b` | `Universality/Circuit/Basic.lean` — `AffineEquation` |
| [`EdouardBonnet/EH-C5`](https://github.com/EdouardBonnet/EH-C5) | `lean` | `63f5c9284f82bad4ea622526b93c4ddfb95fcae6` | `concepts/Lax54/GraphDefinitions.lean` — `C5` |
| [`EdouardBonnet/EH-P5`](https://github.com/EdouardBonnet/EH-P5) | `lean` | `a44fe30b0adfc892f26c29ea5dc7815a3f4f45c3` | `concepts/Lax57/GraphDefinitions.lean` — `P5` |
| [`EdouardBonnet/fine-grained-hypotheses`](https://github.com/EdouardBonnet/fine-grained-hypotheses) | `lean` | `0c66830680856ae535e19462b5bc2af150d308fb` | `concepts/Lax489179/TuringMachine.lean` — `Move` |
| [`EdouardBonnet/moser-tardos`](https://github.com/EdouardBonnet/moser-tardos) | `lean` | `2fc19f8c69c3ae6dc8770629b3613220283ce669` | `concepts/Lax296731/MoserTardosDefinitions.lean` — `TableIndex` |
| [`EgoFakeFantasy/PCFAlephOmega4`](https://github.com/EgoFakeFantasy/PCFAlephOmega4) | `lean` | `1425aaf31aa9168ccbde6a41bcf5a7d2302f4b1b` | `PcfProject/FinitePcf.lean` — `finset_exists_small` |
| [`FormalizedFormalLogic/AlphaCentauri`](https://github.com/FormalizedFormalLogic/AlphaCentauri) | `lean` | `c8c11b032df0dbf6d6e94469259b7a24593089ac` | `AlphaCentauri/Model/Basic.lean` — `EndExtension` |
| [`FredericaBernkastel1/Stochastic-Process-lean-lib`](https://github.com/FredericaBernkastel1/Stochastic-Process-lean-lib) | `lean` | `b609382f2b7f1eb460c48b13072197dfd998f4b7` | `StochLean/ForMathlib/MeasureTheory/QuadraticMeasureAlgebra.lean` — `quadratic_measure_domination_add` |
| [`gdahia/DensityHalesJewett`](https://github.com/gdahia/DensityHalesJewett) | `lean` | `a11ca509eb19594ae724424711964dd2211ea67f` | `DensityHalesJewett/Subspace.lean` — `injective` |
| [`gdanezis/lean-dag`](https://github.com/gdanezis/lean-dag) | `lean` | `e4cb503b96ba7415ab90f944999ec2483953ccc6` | `LeanDag/Adaptive/Headline.lean` — `score_safe` |
| [`guanyangwang/ktv-swap-lean-comparator`](https://github.com/guanyangwang/ktv-swap-lean-comparator) | `lean` | `fd4dc985900b1fba59791067dcf3bf9341a94bda` | `Solution.lean` — `toKTVModel` |
| [`hanyi162013-Yihan/projection-density-theorem-formalization`](https://github.com/hanyi162013-Yihan/projection-density-theorem-formalization) | `lean` | `91cede0789e5ee3613a4ab735c364904818691b4` | `LivshytsProjectionFormalization/ProbabilityCore.lean` — `interval_small_ball_of_bounded_pdf` |
| [`heffordj/TwoMonoidal`](https://github.com/heffordj/TwoMonoidal) | `lean` | `8d50e6dbd58265644cfbd9b06507fcd7d6c9cd12` | `TwoMonoidal/Basic.lean` — `TwoMonoidalStructures` |
| [`ilyasergey/langlib`](https://github.com/ilyasergey/langlib) | `lean` | `38f5a43dc360ea3dc0fdc24b83fa312e1bd17b2c` | `Langlib/Common/Computability.lean` — `TuringComplete` |
| [`itpplasma/algebraic-analysis`](https://github.com/itpplasma/algebraic-analysis) | `lean` | `121596ebe2447b60933a39c378779eabed552902` | `AlgebraicAnalysis/RingTheory/RatFuncAtPoint.lean` — `polynomialAtPoint` |
| [`jaredwilder/additive-combinatorics-campaigns`](https://github.com/jaredwilder/additive-combinatorics-campaigns) | `lean` | `f262fe6fa8371ca1d41da028d783129a83aa862d` | `blade-championship/formal/BvSmoke.lean` — `bvSmoke` |
| [`jaredwilder/erdos-theorems`](https://github.com/jaredwilder/erdos-theorems) | `lean` | `cc8d3a6128d6ece468e04c867d048948b48dab31` | `theorems/cover-C13-6-3/Cover20Degree.lean` — `CoversTriples` |
| [`jaredwilder/erdos138-obstruction`](https://github.com/jaredwilder/erdos138-obstruction) | `lean` | `8f87dd38062535eb50b77973f3e9747b92db16ea` | `E138Fragments.lean` — `RootDiv` |
| [`jaredwilder/erdos74-bipartite-defect`](https://github.com/jaredwilder/erdos74-bipartite-defect) | `lean` | `29d3347da826b82c3717d1318d40aa3bd012f49b` | `research/lean/Attack01.lean` — `edgeDistancesToBipartite` |
| [`jaredwilder/erdos902-tournament-f4`](https://github.com/jaredwilder/erdos902-tournament-f4) | `lean` | `abc594fec27e338297aee91e994991068a9307b6` | `structural-proof/probe.lean` — `row35` |
| [`JD-Jones-ASES/fs-formal`](https://github.com/JD-Jones-ASES/fs-formal) | `lean` | `4e796565301b1425c53e807a6edf408535b2e922` | `FsLowerBound/Defs.lean` — `IsNonzeroSquareMod` |
| [`JD-Jones-ASES/x-ray-lean`](https://github.com/JD-Jones-ASES/x-ray-lean) | `lean` | `c0a7d9f6119ed1126a292081689fdf8927ac12ea` | `XRay/Defs.lean` — `Profile` |
| [`joelcanary/collatz-kodama-observable`](https://github.com/joelcanary/collatz-kodama-observable) | `lean` | `2493cf651c6dfdc61d43051a8cf7377436428330` | `lean/CollatzProof/KodamaFermat.lean` — `step_a` |
| [`karirogg/strong-roberson-conjecture-for-split-off-minors`](https://github.com/karirogg/strong-roberson-conjecture-for-split-off-minors) | `lean` | `f93926d1c29164f03713bfee580bca8898d14014` | `StrongRoberson/Basic.lean` — `MultigraphHom` |
| [`kim-em/erdos-unit-distance-comparator`](https://github.com/kim-em/erdos-unit-distance-comparator) | `lean` | `ea90703b93418edea2cdc7a631b0b4287e47bac4` | `Solution.lean` — `unitDist` |
| [`klavins/polya-topology`](https://github.com/klavins/polya-topology) | `lean` | `7e6c1e25910e72146dbeb4831dd2e128cf641c65` | `PolyaTopology/GeneralTopology/MetricSpaces.lean` — `MetricSpace` |
| [`landonfox00/lean-operads`](https://github.com/landonfox00/lean-operads) | `lean` | `799e1cd8107ace580aa79b76a1a13ae04913a118` | `Operad/Basic.lean` — `reindex` |
| [`linhaowei1/sum-diff-proof`](https://github.com/linhaowei1/sum-diff-proof) | `lean` | `f53f84223b48457ac922836b661227309d9340c3` | `SumDiffExponent.lean` — `growthExponent` |
| [`LR-UK/exp-chaotic`](https://github.com/LR-UK/exp-chaotic) | `lean` | `303b2d3d1121ebc3a86399de8f1e71c17a8b6dd8` | `ExpChaotic/Basic.lean` — `exponentialMap` |
| [`macgregor-sudo/albert-frame-triple-invariants`](https://github.com/macgregor-sudo/albert-frame-triple-invariants) | `lean` | `dd06ef5d423a0e4a5d814d2c221e999b98887ee1` | `AlbertLean/ModelProduct.lean` — `coordToHermitian_productForm_square` |
| [`manitgupta27/A-Topological-Interpretation-of-Divisibility`](https://github.com/manitgupta27/A-Topological-Interpretation-of-Divisibility) | `lean` | `8608c95760553ea987dfd9c9af24c36201bf58f8` | `subspace_topology_semigroup.lean` — `yS_set` |
| [`marco-david/ainfinity-lean`](https://github.com/marco-david/ainfinity-lean) | `lean` | `28684eb7a4d32489f081e2f415118746ff6f48ab` | `AInfinity/AInfinityCategory.lean` — `AInfinityCategoryStruct` |
| [`mario-ullrich/Lean-SNumbers`](https://github.com/mario-ullrich/Lean-SNumbers) | `lean` | `d984f39b53eb1579920fe987de10382dcf553f4e` | `BasicResults/KadetsSnobar.lean` — `exists_projection_range_eq_of_rank_le` |
| [`Matherunner/formalproofs`](https://github.com/Matherunner/formalproofs) | `lean` | `d8f3ec76b3746674984b0f73024645d28186ed42` | `First/Ladder.lean` — `norm3` |
| [`minchaowu/Kruskal.lean4`](https://github.com/minchaowu/Kruskal.lean4) | `lean` | `8b2815bfd3d3ceca9079a1cbb48fe43d2264161e` | `Kruskal/Tree.lean` — `Tree` |
| [`mroximut/dLean`](https://github.com/mroximut/dLean) | `lean` | `04c83a1a488eea298e10439c3e0d4f251cbe8201` | `dLean/Core/ODE.lean` — `Evolvable` |
| [`N-Y-L/quantum-adiabatic-lean`](https://github.com/N-Y-L/quantum-adiabatic-lean) | `lean` | `73b4a2688d0ec6db16be89bd6db13041271adc08` | `Adiabatic/Unbounded/GraphLimit.lean` — `norm_shift_le_of_tendsto_inclusion_of_bound_tendsto` |
| [`nikhgarg/AppliedModelingLib`](https://github.com/nikhgarg/AppliedModelingLib) | `lean` | `2db7d108cd3a2cb10148974bb2a77856e7d87428` | `AppliedModelingLib/Algorithms/Complexity/Classes.lean` — `ComplexityClassModel` |
| [`nitromannitol/Unique-Continuation-Planar`](https://github.com/nitromannitol/Unique-Continuation-Planar) | `lean` | `570e94f540e20dc4698207f0f3eb4f12c8f45e42` | `UCPlanar/Basic.lean` — `UCPlanar.boundedDensity` |
| [`openai/NavierStokesAndEuler`](https://github.com/openai/NavierStokesAndEuler) | `lean` | `f9e8bc5b38b6e212696e8a30e3e91517af887bbd` | `Euler/AllOrderDriftBudget.lean` — `Budget` |
| [`project-numina/kakeya-3d`](https://github.com/project-numina/kakeya-3d) | `lean` | `a26427e3c2fcaf9f98694fbd0d4dd49e41dcf5e3` | `Kakeya/CShading.lean` — `CShadedBody` |
| [`proximity-prize/proximity-prize`](https://github.com/proximity-prize/proximity-prize) | `lean` | `cdb451f13fdc6c84f5fe363e77ee13a89bd30974` | `ProximityPrize/Benchmark/IRSProfile.lean` — `totalDimension` |
| [`r-tanaka-math/mathlib-annex`](https://github.com/r-tanaka-math/mathlib-annex) | `lean` | `6b97ccddc4641d8c8f55b2c3982aa481f4e3b15f` | `MathlibAnnex/Analysis/Normed/Affine/Reflection.lean` — `restrictedPointReflection` |
| [`rchain-community/quantum-logical-framework`](https://github.com/rchain-community/quantum-logical-framework) | `lean` | `e345ac7380d10ca87e8427862ac36511289034dd` | `lean/ER_EPR_QLF.lean` — `ERBridge` |
| [`rollroyces/erdos-125`](https://github.com/rollroyces/erdos-125) | `lean` | `b8d46ebfbe2be682ba956c4b53c8e98087109a9f` | `code/L9_attempt.lean` — `inA` |
| [`roos-j/lean-nct`](https://github.com/roos-j/lean-nct) | `lean` | `412a206c3d6254058d78c0805dabefa735502af0` | `LeanNct/Defs.lean` — `multipleErgodicAverage` |
| [`SamuelSchlesinger/algebraic-circuits`](https://github.com/SamuelSchlesinger/algebraic-circuits) | `lean` | `aa344cfac8c9e74d6847fef41fd88ea386b2244c` | `Algebraic/MassProduction/SortingSemantics/Defs.lean` — `SequenceBitonic` |
| [`SauersML/group-approximation`](https://github.com/SauersML/group-approximation) | `lean` | `c72fa1015c52ce53c9ad9c196b2b71fe346101ff` | `GroupApproximation/AlgTop/ChernMap.lean` — `map` |
| [`ScottCarnahan/vertexAlg`](https://github.com/ScottCarnahan/vertexAlg) | `lean` | `4453e34ec390e82a0c789c731ada8f9a6e86bdea` | `VertexAlg/VertexBasic/Defs.lean` — `stateField` |
| [`sebastianbiallas/sz8-over-q`](https://github.com/sebastianbiallas/sz8-over-q) | `lean` | `1fec485dad123e41af9f5260de2270e452a2ba28` | `lean/Sz8/Galois/IntModel.lean` — `termOK` |
| [`seewoo5/cohn-elkies-refactor`](https://github.com/seewoo5/cohn-elkies-refactor) | `lean` | `9195137d03693486eed0cc98d76a902098e4598d` | `CohnElkiesForMathlib/Topology/Algebra/InfiniteSum/ENat.lean` — `hasSum` |
| [`shosonoda/lean-ridgelet`](https://github.com/shosonoda/lean-ridgelet) | `lean` | `e9af79a1042c19891a9991addb92b75947886343` | `LeanRidgelet/Basic.lean` — `InputSpace` |
| [`sterraf/chain-bounding`](https://github.com/sterraf/chain-bounding) | `lean` | `921d8c068b65882ce3f96b9cc92beb24aa2b224d` | `Solution.lean` — `IsSegment` |
| [`SteveWmoc/riemann-roch`](https://github.com/SteveWmoc/riemann-roch) | `lean` | `7912cc4c7d00854c4ca60a51ec1cb659c70d2782` | `RiemannRoch/ProjectiveLine/BasicOpens.lean` — `scheme` |
| [`subfish-zhou/goldbach-lean`](https://github.com/subfish-zhou/goldbach-lean) | `lean` | `09b97db5764ade1246bfb77206baa1b124760958` | `AnalyticNumberTheory/Mertens/Abelian.lean` — `primeEulerCorrection` |
| [`sweeneyde/1mfld`](https://github.com/sweeneyde/1mfld) | `lean` | `83e961ba28dd8182e7bae844756aba614eb1512e` | `OneMfld/Charts.lean` — `OChart` |
| [`tadamcz/erdos548`](https://github.com/tadamcz/erdos548) | `lean` | `82ffb751f3d37768927df9239ed08439bbe0dd09` | `Erdos548/Resolutions/Erdos548_192usd_21h.lean` — `MarkedEnd` |
| [`thiagomassensini/quantity-representation-foundations`](https://github.com/thiagomassensini/quantity-representation-foundations) | `lean` | `66f9ab46c6fa2622c5e6d9f5ed2c497040c62374` | `QuantityRepresentationFoundations/CarryGeometryNormalizationBridge.lean` — `emergentCoordinates_are_carryGeometryNormalization` |
| [`timaeus-research/grammar`](https://github.com/timaeus-research/grammar) | `lean` | `52b10d534d396dc0dd6a14e4a804418db3783524` | `Grammar/ChartModelGeometry.lean` — `monoPhase` |
| [`Timeroot/InverseGaloisProblem`](https://github.com/Timeroot/InverseGaloisProblem) | `lean` | `a7e7a1748aa9473adf4c508e94615c926f38f81c` | `InverseGalois/NumberTheory/NormSign.lean` — `filter_mk_eq_pair` |
| [`tomdif/eml-lean`](https://github.com/tomdif/eml-lean) | `lean` | `72bfdee3487e9705c58afef21bdfd384c22354e3` | `EML/Basic.lean` — `eml` |
| [`trailofbits/constructive-cryptography`](https://github.com/trailofbits/constructive-cryptography) | `lean` | `e13678ce0876e144a15ca3340f66b650ae41f92b` | `Probability/DistributionMeasure.lean` — `toPMF` |
| [`tunnellm/lean-ieee754`](https://github.com/tunnellm/lean-ieee754) | `lean` | `122bf4ba118e694d32d82a1f67cea27b7f6b8bb6` | `FP/Basic.lean` — `RelativeError` |
| [`turahigashi/hyper-tamari`](https://github.com/turahigashi/hyper-tamari) | `lean` | `5168c78bbfcafe6e2dd21ff2db4d8e6a43253ad6` | `HyperTamari/Basic.lean` — `hyper` |
| [`UCLA-StarAI/ddnnf-negation`](https://github.com/UCLA-StarAI/ddnnf-negation) | `lean` | `276e8b34c0f31221b0670b1a8e067c03ce32bfc7` | `src/DDNNFNegationCorollaries/ProbabilisticSubtraction.lean` — `botCircuit` |
| [`ucsd-formal/constrained-decoding-formalization`](https://github.com/ucsd-formal/constrained-decoding-formalization) | `lean` | `989fd77dc39b7d2e97bee8719a797efa3afac9fc` | `ConstrainedDecodingFormalization/Char.lean` — `ExtChar` |
| [`wwylele/Compass`](https://github.com/wwylele/Compass) | `lean` | `738da583822a43ffa8e6356b9f5629678cf700d7` | `Compass/Basis.lean` — `basis2D` |
| [`xiyin137/OSreconstruction`](https://github.com/xiyin137/OSreconstruction) | `lean` | `4ff9075f579608425a63d997a4a88bec5402af9f` | `Proofideas/paley_wiener_definition_analysis.lean` — `HasOneSidedFourierSupport` |
| [`xukai92/mcmc-lean`](https://github.com/xukai92/mcmc-lean) | `lean` | `58fb038917b505f652ad145294238487e7f798a8` | `formal/Mcmc/Docs/Graph.lean` — `GraphNode` |
| [`yangdabei/ttn-loss-landscape`](https://github.com/yangdabei/ttn-loss-landscape) | `lean` | `b1f47991b435dc930e37e94106dbda1b1acf3821` | `TTN/Landscape/CriticalityBasic.lean` — `instTopologicalSpaceNodeTensor` |
| [`zilberstein/convex-powerset`](https://github.com/zilberstein/convex-powerset) | `lean` | `1ca469942cab628084b9fcd7bcb0958679d184cd` | `ConvexPowerset/Basic.lean` — `ConvexPowerset` |
| [`zilberstein/pomsets-with-formulae`](https://github.com/zilberstein/pomsets-with-formulae) | `lean` | `2cbc9a17ab634218282ea1655da0018ad3d3e0ae` | `Pom/Basic.lean` — `Pom` |
| [`CharlesCNorton/stellarocq`](https://github.com/CharlesCNorton/stellarocq) | `rocq` | `c7acc866eb68a80753eec5bfadd59bab419b2c88` | `theories/Cell.v` — `xeval_agree` |
| [`clayrat/strictness-pcf`](https://github.com/clayrat/strictness-pcf) | `rocq` | `67d26ac615c463c4ffe36cce5638afdd1b909f77` | `theories/LogicalRelation.v` — `term_rel` |
| [`CMU-SAFARI/CertiFlash`](https://github.com/CMU-SAFARI/CertiFlash) | `rocq` | `a1b6a1a4febc1f70feefdea725eb04fe35ceaea6` | `formal-proof/src/core/Model.v` — `Addr` |
| [`formal-dynamics/rocq-dynamics`](https://github.com/formal-dynamics/rocq-dynamics) | `rocq` | `7d734d5c201649704a68208e981f64ac9a1c9283` | `theories/prob/avg.v` — `avg` |
| [`jwiegley/washsale`](https://github.com/jwiegley/washsale) | `rocq` | `4e304665aa9bb9e5febcd3a30bce9a50c9213355` | `doc/probes/Gate1.v` — `corpus10` |
| [`kiranandcode/rupi-c`](https://github.com/kiranandcode/rupi-c) | `rocq` | `f35a51acf5e5077aaf44a457105ab65139d2bd87` | `theories/SQLite/MutexEndG1.v` — `me_start` |
| [`mukeshtiwari/PQ-Crypto`](https://github.com/mukeshtiwari/PQ-Crypto) | `rocq` | `df0c7e6d5e60671244eb3655ec0c636eeb10a64a` | `src/Security/Model.v` — `r_sample_pair_bij` |
| [`mukeshtiwari/SigmaLang`](https://github.com/mukeshtiwari/SigmaLang) | `rocq` | `b02a0e1f55c2b1c362cacec00dd859e8e5f25824` | `Algebra/Group.v` — `group_cancel_right` |
| [`TheFrozenFire/unknown-order`](https://github.com/TheFrozenFire/unknown-order) | `rocq` | `9942418c46e3532e6b925032083ca516fbe3a0e9` | `rocq/BitLogic.v` — `bit_and` |
| [`womeier/local-coalescing`](https://github.com/womeier/local-coalescing) | `rocq` | `7723d4b524106bd4873448ec337e5ca9a2cbbe52` | `theories/pipeline.v` — `parse_and_print` |

| [`LionSR/QICLean`](https://github.com/LionSR/QICLean) | `lean` | `cdaa636d1f41560f7caca7077c11068229cb9727` | `QICLean/Channel/Basic.lean` — `IsChannel` |
| [`Riflonnade/RandomSetTheory`](https://github.com/Riflonnade/RandomSetTheory) | `lean` | `544f98470c3960a282d6f95c6e08c5487a195664` | `RandomSetTheory/AumannExpectation.lean` — `aumannExpectation` |
| [`lean-dojo/FloatLib`](https://github.com/lean-dojo/FloatLib) | `lean` | `40301cd44f253a4ac6ccd34a0eb6c221e185e25c` | `FloatLib/Floats/Formats/BinaryInterchange/Configured/Type.lean` — `Binary` |
| [`aravpaladiya/factorization-theory-formalization`](https://github.com/aravpaladiya/factorization-theory-formalization) | `lean` | `446677f78db920289a200faefe20a5a1db8fdf5f` | `FactorizationTheory/Mathlib/RingTheory/Factorization/BlockMonoid/Basic.lean` — `blockMonoidOver` |
| [`BochaoKong/classical-complex-wpt`](https://github.com/BochaoKong/classical-complex-wpt) | `lean` | `b4a7273fe5c9752753c52e10494097569089642d` | `ClassicalComplexWPT/Basic.lean` — `IsWeierstrassPreparation` |
| [`selpoG/lean-hahn-kaplansky`](https://github.com/selpoG/lean-hahn-kaplansky) | `lean` | `0ac403089dede98ca95868d21e0cd1d484358eec` | `HahnKaplanskyRealClosedness/Basic/HahnField.lean` — `HahnField` |
| [`selpoG/lean-ratfunc-witt-local-global`](https://github.com/selpoG/lean-ratfunc-witt-local-global) | `lean` | `ffe86b61b793a93d6fbd63816be83ab3f9c4b410` | `RatFuncWittLocalGlobal/FiniteDimensional/QuadraticForm.lean` — `diagonalQuadraticForm` |
| [`tvdlinde/snake-lean`](https://github.com/tvdlinde/snake-lean) | `lean` | `40eef824104c8d77480e033acd6dc1ad051b5f19` | `SnakeLean/Normal.lean` — `IsNormal` |
| [`dhsorens/lean-refine`](https://github.com/dhsorens/lean-refine) | `lean` | `fc87328256423a029d8aac6753a1c356c7228ac6` | `Refine/Nres.lean` — `Nres` |
| [`fukubillueda-web/epsilon_FML`](https://github.com/fukubillueda-web/epsilon_FML) | `lean` | `b91ad93900a5e6d9207a4e6166ac94bb3bbcf3ed` | `LanglandsFirstMainLemma/Basic/CharacterTypes.lean` — `ContinuousAddChar` |
| [`hzldew-git/BongTheory`](https://github.com/hzldew-git/BongTheory) | `lean` | `a81fa2edf7d79c7740ea58539b809ce93f1612c0` | `Bong/Bong/Basic.lean` — `BONG` |
| [`EdouardBonnet/cook-levin`](https://github.com/EdouardBonnet/cook-levin) | `lean` | `3481a9cc2e2693124717e398f443f8053629d730` | `concepts/Lax429075/Satisfiability.lean` — `SAT` |
| [`dcposch/jc2-lean`](https://github.com/dcposch/jc2-lean) | `lean` | `6ee763cd623649a5af0517dd12d7202ce2e2ea3c` | `gcd3-69-composition/FaberNormalForm.lean` — `GCD369CubeFaberNormalForm` |
| [`catskillsresearch/platonic-solids`](https://github.com/catskillsresearch/platonic-solids) | `lean` | `ba9e6b50e243473210d6ca0ba6aae81c8d6922a0` | `PlatonicSolids/PlatonicPair.lean` — `IsPlatonicPair` |
| [`meixide/tightness-ring`](https://github.com/meixide/tightness-ring) | `lean` | `6f7fa8ce73e1988052fc215b8e98cc8f26a08fcb` | `TightnessRing/OpRing.lean` — `OP1` |
| [`MichaelStollBayreuth/QuadraticIterates`](https://github.com/MichaelStollBayreuth/QuadraticIterates) | `lean` | `e9e091f5e46b9e5fddee4fb34ca848aa50acf8ba` | `QuadraticIterates/ArchMath1992/Iterates.lean` — `iteratedPoly` |
| [`Cobord/ErrorCorrection`](https://github.com/Cobord/ErrorCorrection) | `lean` | `f88ba4146ecb070687ef7c165e65157bff2a594c` | `ErrorCorrection/LinearECC.lean` — `LinearECC` |
| [`Frisk17/TypeTheory`](https://github.com/Frisk17/TypeTheory) | `lean` | `6236735ae737d404e08d238a96d53c6716b71a06` | `TypeTheory/Untyped/Lambda/LocallyNameless/Basic.lean` — `Term` |
| [`ushironoko/flp-lean`](https://github.com/ushironoko/flp-lean) | `lean` | `4a5cbbad4951e2ecae6bf747c1c0a05efb994bd0` | `FlpLean/Model.lean` — `Protocol` |
| [`EdouardBonnet/immerman-szelepcsenyi`](https://github.com/EdouardBonnet/immerman-szelepcsenyi) | `lean` | `fae3750ccee617c7f97680c6f1ceef3996b3f47e` | `concepts/Lax733996/Counting.lean` — `Census` |
| [`EdouardBonnet/savitch`](https://github.com/EdouardBonnet/savitch) | `lean` | `1062714795609fb441d35a663d6d21fa2fba3a72` | `concepts/Lax307052/ConfigurationGraph.lean` — `graph` |
| [`nickroci/timed-kt`](https://github.com/nickroci/timed-kt) | `lean` | `9816ed9fe6cc16ce29e3d8da475ae36a0df37022` | `TimedKt/Kt.lean` — `Kt_cond` |
| [`YuanheZ/lean-stat-learning-theory`](https://github.com/YuanheZ/lean-stat-learning-theory) | `lean` | `d0f506f0a695018265dccb33bcb05e2f5ca1c876` | `SLT/CoveringNumber.lean` — `coveringNumber` |
| [`itpplasma/navier-formal`](https://github.com/itpplasma/navier-formal) | `lean` | `576b72d43a55a81ca18c9bf87e306a55a9b06cdd` | `NavierFormal/SolutionClass.lean` — `IsClassicalSolution` |
| [`jaumededios/LMLF`](https://github.com/jaumededios/LMLF) | `lean` | `00f4ab46c750d006319066f44115a218c1cc4c62` | `LMLF/Definitions/Gamma.lean` — `gamma_eq_eulerIntegral` |
| [`rdlnmrn/purelib`](https://github.com/rdlnmrn/purelib) | `lean` | `6564360775d0a235ac5781af772fa98131e469dc` | `CCL/Arithmetic/Enclosures.lean` — `Ball` |
| [`jardenadi/Jarden-Shami-Colorings`](https://github.com/jardenadi/Jarden-Shami-Colorings) | `lean` | `7dbf3335844638109946d4c7fad2fec2b6298d46` | `JrSh.lean` — `IsAdditive` |
| [`selpoG/lean-matrix-sos`](https://github.com/selpoG/lean-matrix-sos) | `lean` | `300ad5f2ebe606100661c9d27ca6ffc815fca9b8` | `MatrixSOS/PolyMatrix.lean` — `IsMatrixSOS` |
| [`siqiliu-tsinghua/tautology`](https://github.com/siqiliu-tsinghua/tautology) | `lean` | `261012c7540673d59a4015371b7618b7573d43da` | `Tautology/RealBasic/ModuleBackend/Dedekind/Basic.lean` — `Cut` |
| [`codula-code/SwitchingLemma`](https://github.com/codula-code/SwitchingLemma) | `lean` | `32e195c3482cc07301ec14f163b0ce356a962c98` | `SwitchingLemma.lean` — `DecisionTree` |
| [`leanprover/con-leche`](https://github.com/leanprover/con-leche) | `lean` | `c431b1ca1b7a93486dd3e0440d3ee82abe90ccd0` | `ConLeche/Kernel/Expr.lean` — `Expr` |
| [`Open-Markets-Initiative/omi-lean-definitions`](https://github.com/Open-Markets-Initiative/omi-lean-definitions) | `lean` | `e16fe48bc4fc82dbc75b4cb3be50a89798507f02` | `Omi/Wire.lean` — `decodeUInt_encodeUInt` |
| [`OneRegex/revera`](https://github.com/OneRegex/revera) | `lean` | `55d4c955f421e253aaa4ff339335d818987e4831` | `lean/Ere/Syntax.lean` — `Ere` |
| [`G-course/char-p-NAhodge-formalization`](https://github.com/G-course/char-p-NAhodge-formalization) | `lean` | `46198a786a1b727f4a24717c272ce49b2f2d3b4e` | `LSZ/Objects.lean` — `NilpotentHiggs` |
| [`Hydrodynamical/Vlasov_Meanfield_Formalization`](https://github.com/Hydrodynamical/Vlasov_Meanfield_Formalization) | `lean` | `986b5f1ec2bdf26800ef65daecbe6187f5e4ae4e` | `Vlasov/Vlasov/OT/Wasserstein.lean` — `wasserstein1` |
| [`Polarnova/FABL`](https://github.com/Polarnova/FABL) | `lean` | `164f830312946ccac6e7fdc7bb9493f0149e820d` | `FABL/Chapter02/InfluencesAndDerivatives/BooleanInfluence.lean` — `booleanInfluence` |
| [`cameronfreer/algorithmic-randomness`](https://github.com/cameronfreer/algorithmic-randomness) | `lean` | `6facf35aeaca4c344a6e967bac96dd24b916b673` | `AlgorithmicRandomness/Complexity/PrefixComplexity.lean` — `prefixComplexity` |
| [`cameronfreer/hilbert10`](https://github.com/cameronfreer/hilbert10) | `lean` | `c244a00d838f72d7633c7ddabb742f1f0f5ee665` | `Hilbert10/DPRM.lean` — `dioph_iff_rePred` |
| [`cameronfreer/reverse-mathlib`](https://github.com/cameronfreer/reverse-mathlib) | `lean` | `e299be8e05881c797571041c66af8e6b46ace507` | `ReverseMathlib/Omega/Graph.lean` — `InternalFunction` |
| [`duckki/quantum-computing-lean`](https://github.com/duckki/quantum-computing-lean) | `lean` | `127ace2fa4a00bfb1f2e40fa7ede1a1de7d86ca2` | `QuantumComputing/State.lean` — `PureState` |
| [`gabrielhrs/markovgames`](https://github.com/gabrielhrs/markovgames) | `lean` | `9c90274fd96d6e8cef50a1c5698294af1de635e1` | `Csg/Basic.lean` — `CSG` |
| [`gotrevor/lean-formalizations`](https://github.com/gotrevor/lean-formalizations) | `lean` | `3a24a73416f83c32b4d4a2ac09588524c6291650` | `src/LeanFormalizations/GeometricMeasureTheory/Kakeya2D/Defs.lean` — `IsKakeya` |
| [`gotrevor/lean-gallery`](https://github.com/gotrevor/lean-gallery) | `lean` | `efc72e14c2030842a44dbc7e42850981886fdd03` | `LeanGallery/Logic/Goodstein/Basic.lean` — `goodsteinSeq` |
| [`n-yamaguchi-0729/ProCGroups`](https://github.com/n-yamaguchi-0729/ProCGroups) | `lean` | `6933dfe3f376833421ce10e782108b95ac84bda5` | `Lean4/ProCGroups/CompletedGroupAlgebra/Basic/InClass/LimitAlgebra.lean` — `CompletedGroupAlgebraInClass` |
| [`nhajouji/matrix_category`](https://github.com/nhajouji/matrix_category) | `lean` | `18786f2934ac0e3efe707c1f5c79bdc9f47e4ea0` | `MatrixCategory/Smith.lean` — `smithOne` |
| [`cjyark/cards-formalization-isabelle`](https://github.com/cjyark/cards-formalization-isabelle) | `isabelle` | `4cb91ee101a24e7e80404541b38ac665ea63be84` | `card.thy` — `protocol_correct` |
| [`a1exziegler/mu-recursive`](https://github.com/a1exziegler/mu-recursive) | `isabelle` | `74db39bc34d172d3111875129ce4e150ed450684` | `muRecursive.thy` — `expr` |
| [`haskell-user/mixed-base-number-system-in-coq`](https://github.com/haskell-user/mixed-base-number-system-in-coq) | `rocq` | `ef08f6fa0c9ea197dd8b48867636e3d21d4615d2` | `number_system.v` — `Number` |
| [`haskell-user/permutations-in-coq`](https://github.com/haskell-user/permutations-in-coq) | `rocq` | `5a32872d1363609a5b174e78d3f701982e720868` | `perm.v` — `Perm` |
| [`VvSsNPk/PropAgda`](https://github.com/VvSsNPk/PropAgda) | `agda` | `fc3a4c10eeb847ae6919c9222cbb05ae293772b6` | `Logic-Agda.agda` — `Props` |
| [`njayinthehouse/subtype-agda`](https://github.com/njayinthehouse/subtype-agda) | `agda` | `6d22c3bdc5c0a40833cca52ce763a7aee56b944b` | `MPSS/Subtyping.lagda.md` — `_∣_⊢_⊲[_]_` |
| [`rocq-community/dedekind-reals`](https://github.com/rocq-community/dedekind-reals) | `rocq` | `da4a7452e1d2a8c89558ee72c40535f484415c54` | `theories/Cut.v` — `R_of_Q` |

## Where to look in Mathlib

The subtrees that carry the most relevant material. A search restricted by path lands in the right part of the library faster than a bare name search.

| Path | Content |
| --- | --- |
| `Mathlib/CategoryTheory/` | 1-categories, limits, adjunctions, monads, comma and elements constructions, abelian categories, monoidal and enriched categories, bicategories, sites, sheaves, topoi, localization, triangulated categories. |
| `Mathlib/AlgebraicTopology/` | Simplicial sets, nerves, quasicategories, simplicial homotopy theory. |
| `Mathlib/Condensed/` | Condensed sets and condensed abelian groups. |
| `Mathlib/AlgebraicGeometry/` | Schemes, morphism classes, gluing, Spec and Proj. |
| `Mathlib/Geometry/Manifold/`, `.../Manifold/Riemannian/`, `.../Manifold/VectorBundle/` | Manifolds with corners, immersions, submersions, bordism, Whitney embedding; Riemannian bundles, `IsRiemannianManifold`, path length and Riemannian distance; vector bundles, local frames, covariant derivatives, tensoriality. Upstream Mathlib is adding metric connections, the Koszul formula, and the Levi-Civita pipeline, and [`leanprover-community/physlib`](https://github.com/leanprover-community/physlib) (see the computational table) carries pseudo-Riemannian metrics on top of these classes. Dormant external Riemannian-geometry repositories predate this tree and are superseded by it. |
| `Mathlib/LinearAlgebra/QuadraticForm/`, `Mathlib/LinearAlgebra/BilinearForm/` | Quadratic and bilinear forms, isometries, orthogonality. |
| `Mathlib/LinearAlgebra/RootSystem/` | Root pairings, root systems, Weyl groups. |
| `Mathlib/NumberTheory/`, `Mathlib/RepresentationTheory/` | Number fields, modular forms, L-series, group representations. |

## Category theory, higher structures, type-theory semantics

| Source | Content |
| --- | --- |
| [`emilyriehl/infinity-cosmos`](https://github.com/emilyriehl/infinity-cosmos) | ∞-cosmos theory over Mathlib's quasicategories; formal ∞-category theory. |
| [`sinhp/HoTTLean`](https://github.com/sinhp/HoTTLean) | Groupoid and natural models of HoTT; semantics of type theory. `Groupoids/ClovenIsofibration.lean` holds a complete split-classifier story for groupoids: cloven isofibrations, fiber reindexing, `Γ ⥤ Grpd`, Grothendieck reconstruction. |
| [`sinhp/Poly`](https://github.com/sinhp/Poly) | Polynomial functors and locally cartesian closed categories. |
| [`sinhp/LeanFibredCategories`](https://github.com/sinhp/LeanFibredCategories) | Fibred categories; this development is inactive and has been superseded by the corresponding Mathlib material. |
| [`sinhp/displayed_categories`](https://github.com/sinhp/displayed_categories) | Displayed categories, including fibers, cartesian lifts, and Street fibrations. The repository is inactive and has no LICENSE file. |
| [`kim-em/lean-category-theory`](https://github.com/kim-em/lean-category-theory) | Early category-theory development later incorporated into Mathlib. The repository is archived. |
| [`rzrn/ground_zero`](https://github.com/rzrn/ground_zero) | Homotopy type theory in Lean 4. The repository is archived. |
| [`gebner/hott3`](https://github.com/gebner/hott3) | HoTT *(Lean 3)*. |
| [`rkirov/category-theory-in-context-lean`](https://github.com/rkirov/category-theory-in-context-lean) | Lean companion to Riehl's *Category Theory in Context*. |
| [`awodey/joyal`](https://github.com/awodey/joyal) | Joyal's representation theorem. |
| [`mariovagomarzal/higher_category_theory`](https://github.com/mariovagomarzal/higher_category_theory) | Higher-order categories after Cosme Llópez. |
| [`ivankobe/FactorizationSystems`](https://github.com/ivankobe/FactorizationSystems) | Factorization systems. |
| [`zilberstein/domain-theory`](https://github.com/zilberstein/domain-theory) | Domain theory. |
| [`Verified-zkEVM/PolyFun`](https://github.com/Verified-zkEVM/PolyFun) | Polynomial functors and interaction trees. |
| [`alexkeizer/QPFTypes`](https://github.com/alexkeizer/QPFTypes) | Quotients of polynomial functors; definitional (co)datatypes. |
| [`dagurtomas/LeanCondensed`](https://github.com/dagurtomas/LeanCondensed) | Additional work on condensed mathematics by the author of Mathlib's condensed-mathematics library. |
| [`mattrobball/BridgelandStability`](https://github.com/mattrobball/BridgelandStability) | Bridgeland stability conditions on triangulated categories. |
| [`YijunYuan/HarderNarasimhan`](https://github.com/YijunYuan/HarderNarasimhan) | Harder–Narasimhan theory. |
| [`Paul-Lez/PersistentDecomp`](https://github.com/Paul-Lez/PersistentDecomp) | Structure theorem for persistence modules. |
| [`Dominique-Lawson/Directed-Topology-Lean-4`](https://github.com/Dominique-Lawson/Directed-Topology-Lean-4) | Directed topology. |
| [`peabrainiac/lean-catdg`](https://github.com/peabrainiac/lean-catdg) | Categorical differential geometry. |
| [`riccardobrasca/SDG`](https://github.com/riccardobrasca/SDG) | Synthetic differential geometry. |

## Algebra, number theory, algebraic geometry

| Source | Content |
| --- | --- |
| [`ImperialCollegeLondon/FLT`](https://github.com/ImperialCollegeLondon/FLT) | Ongoing Fermat's Last Theorem formalization with substantial commutative algebra, dimension theory, and number theory. Its `FLT/Mathlib/` staging tree includes upstream-bound files on integral adeles and tensor-versus-restricted-product equivalences. |
| [`leanprover-community/flt-regular`](https://github.com/leanprover-community/flt-regular) | FLT for regular primes; cyclotomic-field material. |
| [`kbuzzard/ClassFieldTheory`](https://github.com/kbuzzard/ClassFieldTheory) | 2025 Clay Summer School project on class field theory. Consumes Mathlib's local-field classes rather than building completion infrastructure; no higher unit groups. |
| [`mariainesdff/LocalClassFieldTheory`](https://github.com/mariainesdff/LocalClassFieldTheory) | Local fields toward local class field theory, including discrete valuation rings, uniformizers, and completions at height-one primes. The repository has no LICENSE file and is incomplete. |
| [`AntoineChambert-Loir/DividedPowers4`](https://github.com/AntoineChambert-Loir/DividedPowers4) | Divided power structures and the divided-power algebra. The core construction is upstreamed in Mathlib `RingTheory/DividedPowerAlgebra/Init`; the grading and polynomial-law layers are not. The repository has no LICENSE file and a partially built source tree. |
| [`YaelDillies/toric`](https://github.com/YaelDillies/toric) | Toric varieties over Mathlib's schemes. |
| [`MichaelStollBayreuth/EulerProducts`](https://github.com/MichaelStollBayreuth/EulerProducts) | Euler products and L-series. |
| [`MichaelStollBayreuth/Heights`](https://github.com/MichaelStollBayreuth/Heights) | Theory of heights. |
| [`CBirkbeck/AINTLIB`](https://github.com/CBirkbeck/AINTLIB) | Atlas of formalized number theory. |
| [`ANR-FALSE/PadicModForms`](https://github.com/ANR-FALSE/PadicModForms) | p-adic modular forms. |
| [`loefflerd/ModularFormDimensions`](https://github.com/loefflerd/ModularFormDimensions) | Finite-dimensionality of modular-form spaces. |
| [`CBirkbeck/ModularForms_Lean4`](https://github.com/CBirkbeck/ModularForms_Lean4) | Modular forms. Much of this material is now incorporated into Mathlib; the repository is inactive. |
| [`CBirkbeck/DirichletNonvanishing`](https://github.com/CBirkbeck/DirichletNonvanishing) | Nonvanishing of Dirichlet L-functions. The repository is archived. |
| [`AlexKontorovich/PrimeNumberTheoremAnd`](https://github.com/AlexKontorovich/PrimeNumberTheoremAnd) | Prime Number Theorem and related analytic number theory. |
| [`math-inc/strongpnt`](https://github.com/math-inc/strongpnt) | Strong prime number theorem with the required complex analysis. The formalization is AI-generated and human-reviewed. |
| [`teorth/expdb`](https://github.com/teorth/expdb) | Exponent-pair database for analytic number theory. |
| [`b-mehta/ABC-Exceptions`](https://github.com/b-mehta/ABC-Exceptions) | Exceptions to the ABC conjecture. |
| [`yawara/odd-order`](https://github.com/yawara/odd-order) | Feit–Thompson odd order theorem in Lean 4, with the finite group theory library it required. |
| [`JobPetrovcic/ArtinWedderburn`](https://github.com/JobPetrovcic/ArtinWedderburn) | Artin–Wedderburn theorem. |
| [`Whysoserioushah/BrauerGroup`](https://github.com/Whysoserioushah/BrauerGroup) | Brauer groups. |
| [`kckennylau/EllipticCurve`](https://github.com/kckennylau/EllipticCurve) | Toward a general definition of elliptic curves over schemes. |
| [`KisaraBlue/ec-tate-lean`](https://github.com/KisaraBlue/ec-tate-lean) | Tate's algorithm for elliptic curves, executable. |
| [`acmepjz/lean-iwasawa`](https://github.com/acmepjz/lean-iwasawa) | Iwasawa theory. |
| [`riccardobrasca/FLT3`](https://github.com/riccardobrasca/FLT3) | Fermat's Last Theorem for exponent 3. |
| [`riccardobrasca/KummerCriterion`](https://github.com/riccardobrasca/KummerCriterion) | Kummer's criterion for regular primes. |
| [`riccardobrasca/kaplanski4`](https://github.com/riccardobrasca/kaplanski4) | Kaplansky's criterion for unique factorization domains. |
| [`chrisflav/bruhat-tits`](https://github.com/chrisflav/bruhat-tits) | The Bruhat–Tits tree. |
| [`smmercuri/adele-ring_locally-compact`](https://github.com/smmercuri/adele-ring_locally-compact) | Local compactness of the adele ring of a number field. |
| [`pitmonticone/QuadraticIntegers`](https://github.com/pitmonticone/QuadraticIntegers) | Rings of integers of quadratic fields. |
| [`MichaelStollBayreuth/Weights`](https://github.com/MichaelStollBayreuth/Weights) | Minimization of hypersurfaces (Elsenhans–Stoll). |
| [`CBirkbeck/uniform-sheafy-tate-domains-lean`](https://github.com/CBirkbeck/uniform-sheafy-tate-domains-lean) | Uniform sheafy Tate rings that are not stably uniform; Huber/Tate ring examples. |
| [`BochaoKong/nullstellensatz`](https://github.com/BochaoKong/nullstellensatz) | Local complex-analytic geometry: Rückert Nullstellensatz and foundations. |
| [`Mathias-Stout/Many-sorted-model-theory`](https://github.com/Mathias-Stout/Many-sorted-model-theory) | Many-sorted logic toward the model theory of valued fields. |
| [`WuProver/groebner_proj`](https://github.com/WuProver/groebner_proj) | Gröbner basis theory; companions [`WuProver/MonomialOrderedPolynomial`](https://github.com/WuProver/MonomialOrderedPolynomial) and [`WuProver/GroebnerTactic`](https://github.com/WuProver/GroebnerTactic). |
| [`Hagb/lean-groebner`](https://github.com/Hagb/lean-groebner) | Gröbner bases, independent development. |
| [`JJYYY-JJY/lean-normal-forms`](https://github.com/JJYYY-JJY/lean-normal-forms) | Executable Hermite and Smith normal forms over Euclidean domains, with proofs relating them to Mathlib's definitions. |
| [`LieLean/LowDimSolvClassification`](https://github.com/LieLean/LowDimSolvClassification) | Classification of solvable Lie algebras of dimension at most three. |
| [`kkytola/VirasoroProject`](https://github.com/kkytola/VirasoroProject) | Witt algebra cohomology and the Virasoro algebra. |
| [`singerng/steinberg-formalization`](https://github.com/singerng/steinberg-formalization) | Steinberg groups. |
| [`npflueger/demazure`](https://github.com/npflueger/demazure) | Demazure products. |
| [`Antoine-dSG/frieze_patterns`](https://github.com/Antoine-dSG/frieze_patterns) | Coxeter's frieze patterns. |
| [`wupr/order-p-q`](https://github.com/wupr/order-p-q) | Classification of groups of order pq. |
| [`Luka-O/polya-enumeration-theorem`](https://github.com/Luka-O/polya-enumeration-theorem) | Pólya enumeration theorem. |
| [`wwylele/PentagonalNumberTheorem`](https://github.com/wwylele/PentagonalNumberTheorem) | Euler's pentagonal number theorem. |
| [`b-mehta/PrimeCert`](https://github.com/b-mehta/PrimeCert) | Formal prime certificates. |
| [`hanwenzhu/miller-rabin`](https://github.com/hanwenzhu/miller-rabin) | Miller–Rabin primality test. |
| [`amellendijk/selberg-sieve4`](https://github.com/amellendijk/selberg-sieve4) | The Selberg sieve. |
| [`samuelborza/IsTranscendentalPi`](https://github.com/samuelborza/IsTranscendentalPi) | Transcendence of π. |
| [`ahhwuhu/zeta_3_irrational`](https://github.com/ahhwuhu/zeta_3_irrational) | Irrationality of ζ(3). |
| [`teorth/sendov`](https://github.com/teorth/sendov) | Sendov's conjecture work. |
| [`AxiomMath/fel-polynomial`](https://github.com/AxiomMath/fel-polynomial) | Fel's conjecture on syzygies of numerical semigroups. This is an AI-formalized paper companion; related formalizations include [`AxiomMath/lattice-triangle`](https://github.com/AxiomMath/lattice-triangle), [`AxiomMath/partial-regularity`](https://github.com/AxiomMath/partial-regularity), and [`AxiomMath/PartitionPolynomial`](https://github.com/AxiomMath/PartitionPolynomial). |
| [`math-inc/FrontierMathOpen-Hypergraphs`](https://github.com/math-inc/FrontierMathOpen-Hypergraphs) | Formalization of a FrontierMath open problem on hypergraphs. Related formalization benchmark: [`math-inc/FormalQualBench`](https://github.com/math-inc/FormalQualBench). |

## Quadratic forms, lattices, sphere packing

| Source | Content |
| --- | --- |
| [`thefundamentaltheor3m/Sphere-Packing-Lean`](https://github.com/thefundamentaltheor3m/Sphere-Packing-Lean) | Viazovska's dimension-8 sphere-packing theorem and the E8 lattice. |
| [`mariainesdff/HassePrinciple`](https://github.com/mariainesdff/HassePrinciple) | Hilbert symbols and the Hasse–Minkowski invariant over general fields (Women in Numbers 7). Definitions are present; some choice-independence proofs remain incomplete. Apache-2.0; the project does not accept outside contributions. |
| [`roed-math/gq2-lean`](https://github.com/roed-math/gq2-lean) | Dyadic Hilbert symbol over ℚ₂ with Serre's evaluation formula and 2-adic square-class facts; all proofs are complete. Apache 2.0. |
| [`MichaelStollBayreuth/LegendreQF`](https://github.com/MichaelStollBayreuth/LegendreQF) | Legendre's theorem on diagonal ternary quadratic forms; complete but defines no Hilbert symbol, Hasse invariant, or lattice notion. |
| [`jonhanke/quadratic_forms_in_lean`](https://github.com/jonhanke/quadratic_forms_in_lean) | Quadratic forms, with Cassels references and a small collection of definitions. The repository contains no theorems and has no LICENSE file. |
| [`leanprover/hex-lll`](https://github.com/leanprover/hex-lll) | Verified LLL lattice-basis reduction with a proved short-vector bound; a companion library proves correspondence with Mathlib's lattice definitions. |
| [`Jun2M/Main-theorem-of-polytopes`](https://github.com/Jun2M/Main-theorem-of-polytopes) | Main theorem of polytopes. |
| [`jsm28/AperiodicMonotilesLean`](https://github.com/jsm28/AperiodicMonotilesLean) | Formalization of the aperiodic monotiles known as the hat and spectre. |
| [`dwrensha/Rupert.lean`](https://github.com/dwrensha/Rupert.lean) | The Rupert problem for convex polyhedra; with [`jcreedcmu/Noperthedron`](https://github.com/jcreedcmu/Noperthedron). |
| [`vasnesterov/HadwigerNelson`](https://github.com/vasnesterov/HadwigerNelson) | Hadwiger–Nelson bounds. |

## Analysis, probability, geometry, dynamics

| Source | Content |
| --- | --- |
| [`teorth/analysis`](https://github.com/teorth/analysis) | Lean companion to Tao's *Analysis I*. |
| [`fpvandoorn/carleson`](https://github.com/fpvandoorn/carleson) | Carleson's theorem. |
| [`fpvandoorn/BonnAnalysis`](https://github.com/fpvandoorn/BonnAnalysis) | Bonn collaborative analysis seminar (distributions, duality). |
| [`leanprover-community/sphere-eversion`](https://github.com/leanprover-community/sphere-eversion) | Sphere eversion via convex integration; h-principle. |
| [`RemyDegenne/brownian-motion`](https://github.com/RemyDegenne/brownian-motion) | Construction of Brownian motion. |
| [`RemyDegenne/testing-lower-bounds`](https://github.com/RemyDegenne/testing-lower-bounds) | Information theory and hypothesis-testing bounds. |
| [`oliver-butterley/SpectralThm`](https://github.com/oliver-butterley/SpectralThm) | Spectral theorem. |
| [`girving/ray`](https://github.com/girving/ray) | Mandelbrot-set results. |
| [`girving/interval`](https://github.com/girving/interval) | Verified floating-point interval arithmetic. |
| [`leanprover-community/lean-liquid`](https://github.com/leanprover-community/lean-liquid) | Liquid Tensor Experiment *(Lean 3; condensed foundations now in Mathlib)*. |
| [`leanprover-community/lean-perfectoid-spaces`](https://github.com/leanprover-community/lean-perfectoid-spaces) | Perfectoid spaces *(Lean 3)*. |
| [`dagurtomas/lean-solid`](https://github.com/dagurtomas/lean-solid) | Solid abelian groups. The repository is inactive. |
| [`ImperialCollegeLondon/condensed-sets`](https://github.com/ImperialCollegeLondon/condensed-sets) | Early condensed mathematics *(Lean 3)*. |
| [`AlexKontorovich/CoveringSpacesProject`](https://github.com/AlexKontorovich/CoveringSpacesProject) | Covering spaces and universal covers; overlaps the [Tau Ceti](https://github.com/TauCetiProject/TauCeti) universal-covers roadmap. |
| [`mccorvie/classification-of-surfaces`](https://github.com/mccorvie/classification-of-surfaces) | Classification of compact surfaces. |
| [`loganrjmurphy/LeanEuclid`](https://github.com/loganrjmurphy/LeanEuclid) | Formal System E for Euclidean geometry, Book I of Euclid's *Elements*, and the UniGeo formalized problem corpus. |
| [`urkud/SardMoreira`](https://github.com/urkud/SardMoreira) | Moreira's version of Sard's theorem; with [`fpvandoorn/sard`](https://github.com/fpvandoorn/sard). |
| [`kebekus/ProjectVD`](https://github.com/kebekus/ProjectVD) | Value distribution theory (Nevanlinna). |
| [`vbeffara/RMT4`](https://github.com/vbeffara/RMT4) | The Riemann mapping theorem. |
| [`scottnarmstrong/DeGiorgi`](https://github.com/scottnarmstrong/DeGiorgi) | De Giorgi–Nash–Moser theory. |
| [`uda-lab/leray-hopf`](https://github.com/uda-lab/leray-hopf) | Leray–Hopf weak solutions of incompressible Navier–Stokes. |
| [`weiran-sun/pde`](https://github.com/weiran-sun/pde) | PDE formalizations. |
| [`RemyDegenne/brownian-motion`](https://github.com/RemyDegenne/brownian-motion) | Construction of Brownian motion; with [`RemyDegenne/kolmogorov_extension4`](https://github.com/RemyDegenne/kolmogorov_extension4). |
| [`cameronfreer/exchangeability`](https://github.com/cameronfreer/exchangeability) | Exchangeability and three proofs of de Finetti's theorem. |
| [`YellPika/quasi-borel-spaces`](https://github.com/YellPika/quasi-borel-spaces) | Quasi-Borel spaces. |
| [`mrdouglasny/OSforGFF`](https://github.com/mrdouglasny/OSforGFF) | Gaussian free field in d=4 and the Osterwalder–Schrader axioms. Same author: [`gaussian-field`](https://github.com/mrdouglasny/gaussian-field), [`lgt`](https://github.com/mrdouglasny/lgt) (lattice gauge theory), [`pphi2`](https://github.com/mrdouglasny/pphi2) (φ⁴₂ construction), [`seiberg-witten`](https://github.com/mrdouglasny/seiberg-witten), [`jacobian-challenge`](https://github.com/mrdouglasny/jacobian-challenge) (compact Riemann surfaces, period lattices, Jacobians, Abel–Jacobi, Riemann bilinear/period matrices, theta foundations), [`hille-yosida`](https://github.com/mrdouglasny/hille-yosida), [`markov-semigroups`](https://github.com/mrdouglasny/markov-semigroups), [`spectral-positivity`](https://github.com/mrdouglasny/spectral-positivity) (Perron–Frobenius, Jentzsch). |
| [`FredRaj3/SemicircleLaw`](https://github.com/FredRaj3/SemicircleLaw) | Wigner's semicircle law. |
| [`dududuguo/HighDimProb`](https://github.com/dududuguo/HighDimProb) | High-dimensional probability, random matrices, concentration. |
| [`lua-vr/pointwise-birkhoff`](https://github.com/lua-vr/pointwise-birkhoff) | Pointwise Birkhoff ergodic theorem. |
| [`kkytola/ExtremeValueProject`](https://github.com/kkytola/ExtremeValueProject) | Fisher–Tippett–Gnedenko theorem. |
| [`roos-j/lean-booleanfun`](https://github.com/roos-j/lean-booleanfun) | Analysis of Boolean functions, including Arrow's theorem. |
| [`sven-manthe/A-formalization-of-Borel-determinacy-in-Lean`](https://github.com/sven-manthe/A-formalization-of-Borel-determinacy-in-Lean) | Borel determinacy. |
| [`YnirPaz/PCF-Theory`](https://github.com/YnirPaz/PCF-Theory) | PCF theory. |
| [`VTrelat/ZFLean`](https://github.com/VTrelat/ZFLean) | Set-theoretic development framework. |

## Combinatorics, discrete mathematics, logic, foundations

| Source | Content |
| --- | --- |
| [`teorth/equational_theories`](https://github.com/teorth/equational_theories) | Implication graph between magma equational laws. |
| [`teorth/pfr`](https://github.com/teorth/pfr) | Polynomial Freiman–Ruzsa conjecture and related additive combinatorics. |
| [`YaelDillies/cam-combi`](https://github.com/YaelDillies/cam-combi) (formerly `LeanCamCombi`) | Cambridge graph theory and combinatorics courses. |
| [`YaelDillies/apap`](https://github.com/YaelDillies/apap) (formerly `LeanAPAP`) | Kelley–Meka bound on Roth numbers. |
| [`apnelson1/Matroid`](https://github.com/apnelson1/Matroid) | Matroid theory over Mathlib. |
| [`Ivan-Sergeyev/seymour`](https://github.com/Ivan-Sergeyev/seymour) | Seymour's decomposition theorem for regular matroids. |
| [`madvorak/vcsp`](https://github.com/madvorak/vcsp) | General-valued constraint satisfaction. |
| [`madvorak/duality`](https://github.com/madvorak/duality) | Linear-programming duality. |
| [`siddhartha-gadgil/Polylean`](https://github.com/siddhartha-gadgil/Polylean) | Group extensions and torsion-freeness with computational proofs. |
| [`leanprover-community/con-nf`](https://github.com/leanprover-community/con-nf) | Consistency of Quine's New Foundations. |
| [`flypitch/flypitch`](https://github.com/flypitch/flypitch) | Independence of the continuum hypothesis *(Lean 3)*. |
| [`FormalizedFormalLogic/Foundation`](https://github.com/FormalizedFormalLogic/Foundation) | Mathematical logic: completeness, incompleteness, provability logic. |
| [`avigad/lamr`](https://github.com/avigad/lamr) | *Logic and Mechanized Reasoning* textbook and code. |
| [`vihdzp/combinatorial-games`](https://github.com/vihdzp/combinatorial-games) | Combinatorial game theory. |
| [`leanprover-community/add-combi`](https://github.com/leanprover-community/add-combi) | Mathlib's additive-combinatorics sublibrary. |
| [`YaelDillies/cam-combi`](https://github.com/YaelDillies/cam-combi) | Cambridge Part II/III graph theory, combinatorics, extremal and probabilistic combinatorics. Same author: [`mean-fourier`](https://github.com/YaelDillies/mean-fourier), [`gibbs-measure`](https://github.com/YaelDillies/gibbs-measure), [`forbidden-matrix`](https://github.com/YaelDillies/forbidden-matrix), [`chandra-furst-lipton`](https://github.com/YaelDillies/chandra-furst-lipton). |
| [`b-mehta/AharoniKorman`](https://github.com/b-mehta/AharoniKorman) | Disproof of the Aharoni–Korman conjecture. |
| [`celioboulay/expander-graphs`](https://github.com/celioboulay/expander-graphs) | Expander graphs. |
| [`mitchell-horner/ErdosStoneSimonovitsKovariSosTuran`](https://github.com/mitchell-horner/ErdosStoneSimonovitsKovariSosTuran) | Erdős–Stone–Simonovits and Kővári–Sós–Turán theorems. |
| [`DhyeyMavani2003/chip-firing-with-lean`](https://github.com/DhyeyMavani2003/chip-firing-with-lean) | Chip-firing games and Riemann–Roch for graphs. |
| [`SamuelSchlesinger/sensitivity-conjecture`](https://github.com/SamuelSchlesinger/sensitivity-conjecture) | Huang's proof of the sensitivity conjecture. Related work by the same author: [`complexitylib`](https://github.com/SamuelSchlesinger/complexitylib). |
| [`PierreSenellart/descriptive-complexity`](https://github.com/PierreSenellart/descriptive-complexity) | Descriptive complexity: NP-completeness via first-order reductions. |
| [`ctchou/AutomataTheory`](https://github.com/ctchou/AutomataTheory) | Automata theory. |
| [`madvorak/chomsky`](https://github.com/madvorak/chomsky) | Chomsky hierarchy and formal grammars. |
| [`FormalizedFormalLogic/Incompleteness`](https://github.com/FormalizedFormalLogic/Incompleteness) | Incompleteness theorems; with [`FormalizedFormalLogic/ProvabilityLogic`](https://github.com/FormalizedFormalLogic/ProvabilityLogic). |
| [`codyroux/traat-lean`](https://github.com/codyroux/traat-lean) | Selected lemmas from *Term Rewriting and All That*. |

## Computational and applied mathematics

| Source | Content |
| --- | --- |
| [`lecopivo/SciLean`](https://github.com/lecopivo/SciLean) | Scientific computing. |
| [`leanprover-community/physlib`](https://github.com/leanprover-community/physlib) (formerly PhysLean/HepLean) | Formalized mathematical physics in Lean, including Riemannian and pseudo-Riemannian geometry, tensor calculus, relativity, distributions, Lie groups, crystal lattices, topological field theory, and lattice quantum field theory. |
| [`Timeroot/Lean-QuantumInfo`](https://github.com/Timeroot/Lean-QuantumInfo) | Quantum information theory. |
| [`optsuite/optlib`](https://github.com/optsuite/optlib) | Optimization algorithms and convergence proofs. |
| [`verified-optimization/CvxLean`](https://github.com/verified-optimization/CvxLean) | Convex optimization modeling. The repository is inactive. |
| [`ufmg-smite/lean-smt`](https://github.com/ufmg-smite/lean-smt) | Automated proof tactics using satisfiability-modulo-theories solvers. |
| [`eric-wieser/lean-matrix-cookbook`](https://github.com/eric-wieser/lean-matrix-cookbook) | The Matrix Cookbook, proved. |
| [`leanprover/cslib`](https://github.com/leanprover/cslib) | Computer science library. |
| [`leanprover-community/iris-lean`](https://github.com/leanprover-community/iris-lean) | Iris separation logic port. |
| [`or4nge19/NeuralNetworks`](https://github.com/or4nge19/NeuralNetworks) | Neural networks. |
| [`shetzl/autth`](https://github.com/shetzl/autth) | Automata theory. |
| [`leanprover/hex`](https://github.com/leanprover/hex) | Hex verified computational algebra; see the [Lean FRO](https://lean-lang.org/fro/) section below for the full library table. |
| [`todbeibrot/Lean-Oscar`](https://github.com/todbeibrot/Lean-Oscar) | Interface between Lean 4 and the [OSCAR](https://www.oscar-system.org/) computer-algebra system. |
| [`girving/series`](https://github.com/girving/series) | Power series arithmetic, with related formalizations of Böttcher series and verified Mandelbrot rendering. |
| [`alerad/LeanCert`](https://github.com/alerad/LeanCert) | Verified interval arithmetic: bounds on exp, sin, cos; root finding. |
| [`Timeroot/computableReal`](https://github.com/Timeroot/computableReal) | Computable real numbers. |
| [`josephmckinsey/Flean`](https://github.com/josephmckinsey/Flean) | Floating-point numbers, replacing `Mathlib.Data.FP`; with [`Beneficial-AI-Foundation/FloatSpec`](https://github.com/Beneficial-AI-Foundation/FloatSpec). |
| [`alok/lean-inf`](https://github.com/alok/lean-inf) | Levi-Civita field for infinitesimal computation. |
| [`Verified-zkEVM/CompPoly`](https://github.com/Verified-zkEVM/CompPoly) | Computable polynomials. |
| [`leanprover/sos`](https://github.com/leanprover/sos) | Sum-of-squares tactic for nonlinear real arithmetic. |
| [`lecopivo/LeanBLAS`](https://github.com/lecopivo/LeanBLAS) | BLAS bindings and specification. |
| [`leanprover/TensorLib`](https://github.com/leanprover/TensorLib) | Verified tensor library. |
| [`astrainfinita/algorithm`](https://github.com/astrainfinita/algorithm) | Verified efficient algorithms. |
| [`GasStationManager/ArtificialAlgorithms`](https://github.com/GasStationManager/ArtificialAlgorithms) | Verified algorithms implemented and proved by AIs. |
| [`LeanMachineLearning/LML`](https://github.com/LeanMachineLearning/LML) | Lean Machine Learning Library. |
| [`Hayata-Yamasaki-Group/lean-quantum`](https://github.com/Hayata-Yamasaki-Group/lean-quantum) | Quantum information and computation; with [`inQWIRE/quantumlib`](https://github.com/inQWIRE/quantumlib). |
| [`LionSR/TNLean`](https://github.com/LionSR/TNLean) | Tensor networks: fundamental theorem of matrix product states, canonical forms. |
| [`formal-applied-math/formal-mathfin`](https://github.com/formal-applied-math/formal-mathfin) | Mathematical finance: Black–Scholes, Itô calculus, FTAP, Girsanov. |
| [`Lean-MoDS/StatsMLlib`](https://github.com/Lean-MoDS/StatsMLlib) | Verified probability, statistics, and learning theory; with [`Robby955/FormalSLT`](https://github.com/Robby955/FormalSLT). |
| [`math-xmum/Gametheory`](https://github.com/math-xmum/Gametheory) | Nash equilibrium via Scarf and Brouwer. |

## Statement banks and generated corpora — always search these

| Source | Content |
| --- | --- |
| [`google-deepmind/formal-conjectures`](https://github.com/google-deepmind/formal-conjectures) | Formalized conjecture statements. When it has a relevant one, import, reuse, or extend it — never restate it from scratch. Sanctioned home for genuinely-unproved deep statements (conjecture ledger, issue #21). |
| [`facebookresearch/atlas-lean`](https://github.com/facebookresearch/atlas-lean) | ATLAS Autoformalized Textbook Library At Scale. Search for textbook definitions, statements, and dependency chains before reconstructing standard mathematics from prose. |
| [`facebookresearch/algebraic-combinatorics`](https://github.com/facebookresearch/algebraic-combinatorics) | Automatic formalization of Grinberg's *Algebraic Combinatorics*. |
| [`facebookresearch/autoform-bot`](https://github.com/facebookresearch/autoform-bot), [`facebookresearch/repoprover`](https://github.com/facebookresearch/repoprover) | ATLAS formalization pipeline and textbook-formalization research code; use to locate generated corpora and source projects. |
| [`facebookresearch/LeanUniverse`](https://github.com/facebookresearch/LeanUniverse) | Index and manager of Lean libraries and datasets. |
| [`facebookresearch/abel`](https://github.com/facebookresearch/abel), [`facebookresearch/Evariste`](https://github.com/facebookresearch/Evariste) | Proof-search systems and their corpora. |
| [`dwrensha/compfiles`](https://github.com/dwrensha/compfiles) | Catalog of formalized competition problems. |
| [`ShouqiaoW/erdos`](https://github.com/ShouqiaoW/erdos) | Erdős problems: checked proofs, partially formalized in Lean. |
| [`trishullab/PutnamBench`](https://github.com/trishullab/PutnamBench) | Putnam problems in Lean 4, Isabelle, and Coq. |
| [`google-deepmind/alphaproof-nexus-results`](https://github.com/google-deepmind/alphaproof-nexus-results) | AlphaProof-generated Lean proofs with prose companions. |
| [`google-deepmind/debate`](https://github.com/google-deepmind/debate) | AI-generated formalized conjecture and theorem statement bank. |
| [`google-deepmind/formal-putnam-like`](https://github.com/google-deepmind/formal-putnam-like) | Formalized Putnam-like olympiad problems and companion statements. |
| [`google-deepmind/miniF2F`](https://github.com/google-deepmind/miniF2F) | Formalized miniF2F benchmark statements and proofs in Lean. |
| [`mo271/FormalBook`](https://github.com/mo271/FormalBook) | Aigner–Ziegler, *Proofs from THE BOOK*. |
| [`lean-dojo/LeanMillenniumPrizeProblems`](https://github.com/lean-dojo/LeanMillenniumPrizeProblems) | Formal statements of the Millennium Prize Problems. |
| [`google-deepmind/formal-imo`](https://github.com/google-deepmind/formal-imo) | IMO problem statements; with [`google-deepmind/formal-putnam-like`](https://github.com/google-deepmind/formal-putnam-like), [`google-deepmind/miniF2F`](https://github.com/google-deepmind/miniF2F), and [`google-deepmind/debate`](https://github.com/google-deepmind/debate). |
| [`carlok/LeanFrontier`](https://github.com/carlok/LeanFrontier) | Machine-generated, kernel-verified mathematics. |
| [`agenticsnz/unsorry`](https://github.com/agenticsnz/unsorry) | Autonomous agents proving theorems; git is the queue. |
| [`leanprover/lean-eval`](https://github.com/leanprover/lean-eval) | [Comparator](https://github.com/leanprover/comparator)-based formal-mathematics evaluation. |
| [`kim-em/lean-training-data`](https://github.com/kim-em/lean-training-data) | Tooling to extract training data from Lean projects. |
| [`kim-em/erdos-unit-distance`](https://github.com/kim-em/erdos-unit-distance) | Alpöge's disproof of the uniform-constant Erdős unit-distance conjecture; the [Palomar](https://palomar-registry.org/) example submission. Other Erdős-problem repos: [`davidturturean/erdos-870`](https://github.com/davidturturean/erdos-870), [`Parcly-Taxel/Redhill`](https://github.com/Parcly-Taxel/Redhill). |

## Lean FRO and Mathlib Initiative projects

The [Lean FRO](https://lean-lang.org/fro/) runs three AI projects ([Year 4 Part 1 roadmap](https://lean-lang.org/fro/roadmap/y4-1/), September 2026 to February 2027). [Tau Ceti](https://github.com/TauCetiProject/TauCeti) is a growing foundational library downstream of Mathlib. [Hex](https://github.com/leanprover/hex) is Mathlib-free verified computation — LLL reduction, determinants, Gram-Schmidt — with Mathlib correspondence proofs. [Palomar](https://palomar-registry.org/) indexes already-verified statements pinned to exact commits, which makes it the fastest place to check whether a named result is done. Entries in this section resolved on GitHub on 2026-09-09.

| Source | Content |
| --- | --- |
| [`TauCetiProject/TauCeti`](https://github.com/TauCetiProject/TauCeti) ([site](https://taucetiproject.github.io/TauCeti/)) | AI-authored Lean library downstream of Mathlib, incubated by the [Lean FRO](https://lean-lang.org/fro/) and the [Mathlib Initiative](https://mathlib-initiative.org/): humans own the roadmap, AI agents author the proofs, AI reviewers gate every PR against open adversarial rubrics. Roadmap themes: universal covers, the Jacobian challenge, reductive algebraic groups, PDE, Heegaard Floer and grid homology, multiquadratic fields and genus theory, geometric topology. Worth searching for anything foundational; [Palomar](https://palomar-registry.org/) allows it as a statement dependency. |
| [`TauCetiProject/TauCetiRoadmap`](https://github.com/TauCetiProject/TauCetiRoadmap) | The human-controlled roadmaps: one `README.md` specification per area plus `Suggested.lean` target signatures. Read it to learn what [Tau Ceti](https://github.com/TauCetiProject/TauCeti) intends to formalize next. |
| [`TauCetiProject/TauCetiReview`](https://github.com/TauCetiProject/TauCetiReview) | The review rubrics (scope, correctness, reuse, attribution, API design, generality, placement, naming, documentation, proof quality, deprecation) and the machinery that runs review. A reference rubric set for adversarial review of AI-written Lean here. |
| [`kim-em/TauCetiWorker`](https://github.com/kim-em/TauCetiWorker) | The contributor agent loop (`uv tool install git+https://github.com/kim-em/TauCetiWorker`, then `tauceti work --loop`); reference implementation of a roadmap-driven Lean worker. |
| [`leanprover/hex`](https://github.com/leanprover/hex) ([manual](https://kim-em.github.io/hex-dev/), [Reservoir](https://reservoir.lean-lang.org/@kim-em/Hex)) | Verified computational algebra in Lean 4, including matrices, row reduction, determinants, Gram–Schmidt orthogonalization, and LLL lattice reduction. The released aggregator; `import Hex` re-exports every released library at one pinned set. Add with `[[require]] name = "hex", git = "https://github.com/leanprover/hex"`. |
| [`leanprover/hex-basic`](https://github.com/leanprover/hex-basic), [`hex-matrix`](https://github.com/leanprover/hex-matrix), [`hex-row-reduce`](https://github.com/leanprover/hex-row-reduce), [`hex-determinant`](https://github.com/leanprover/hex-determinant), [`hex-bareiss`](https://github.com/leanprover/hex-bareiss), [`hex-gram-schmidt`](https://github.com/leanprover/hex-gram-schmidt), [`hex-lll`](https://github.com/leanprover/hex-lll) | The Mathlib-free computational libraries: dense matrices, row reduction, nullspaces, determinants (Bareiss over `Int`), Gram–Schmidt, and a verified LLL lattice-basis reduction with a proved short-vector bound, plus a checked-oracle mode over [fplll](https://github.com/fplll/fplll). Optimized for runtime first and kernel reduction second; runtime bodies are `@[csimp]` twins, never `@[implemented_by]`. |
| [`leanprover/hex-matrix-mathlib`](https://github.com/leanprover/hex-matrix-mathlib), [`hex-row-reduce-mathlib`](https://github.com/leanprover/hex-row-reduce-mathlib), [`hex-determinant-mathlib`](https://github.com/leanprover/hex-determinant-mathlib), [`hex-bareiss-mathlib`](https://github.com/leanprover/hex-bareiss-mathlib), [`hex-gram-schmidt-mathlib`](https://github.com/leanprover/hex-gram-schmidt-mathlib), [`hex-lll-mathlib`](https://github.com/leanprover/hex-lll-mathlib) | The Mathlib bridges: correspondence proofs between each [Hex](https://github.com/leanprover/hex) computation and Mathlib's definitions, transported typeclass instances, and theorems whose proofs need Mathlib. This is the layer a `Realization` here would consume. |
| [`kim-em/hex-dev`](https://github.com/kim-em/hex-dev) | The development monorepo: `SPEC/SPEC.md`, `SPEC/design-principles.md`, `PLAN.md`, `libraries.yml`, `bench/`, `conformance/`. Unreleased libraries (polynomial arithmetic, Hensel lifting, Berlekamp–Zassenhaus factoring, algebraic numbers) live here; released repositories are generated mirrors, never edited by hand. Its design principles (many small libraries, no Mathlib in the computational core, checked external oracles, conformance and benchmark gates before proofs) are the reference for any verified-computation layer in `lean-cas-dsl`. |
| [Palomar](https://palomar-registry.org/) ([about](https://palomar-registry.org/about), [how to submit](https://palomar-registry.org/how-to-submit), [`PalomarRegistry/PalomarPolicy`](https://github.com/PalomarRegistry/PalomarPolicy), [`PalomarRegistry/PalomarTemplate`](https://github.com/PalomarRegistry/PalomarTemplate)) | Registry of Lean-verified mathematical results, incubated by the [Lean FRO](https://lean-lang.org/fro/) and [ICARM](https://icarm.io/). Each entry pins a 40-character commit, a short `Challenge.lean` statement (hard cap 1,000 lines), a `Solution.lean` proof, a [Comparator](https://github.com/leanprover/comparator) configuration, and a `formalization.yaml`; proofs are replayed through Lean's kernel and the independent [NanoDa](https://github.com/ammkrn/nanoda_lib) kernel, and a language model checks the informal-to-formal correspondence. Search it for already-registered statements before formalizing; the template repository is the layout to use when publishing a result from here. |
| [`leanprover/comparator`](https://github.com/leanprover/comparator) | Comparator: judges that a `Solution` module proves exactly the theorems stated in a `Challenge` module, with sandboxing (`landrun`), `lean4export`, permitted-axiom checks, and optional [`ammkrn/nanoda_lib`](https://github.com/ammkrn/nanoda_lib) replay. Required by [Palomar](https://palomar-registry.org/); the FRO plans a `lake check` command that ships it in the Lean distribution. |
| [`mathlib-initiative/formalization.yaml`](https://github.com/mathlib-initiative/formalization.yaml) | Self-reporting standard (v0.4, with JSON schema) for formalization projects: provenance, sources and their relationship (`formalizes`, `adapts`, `independently-proves`, `background`), AI use, fidelity, scope, review status. [Palomar](https://palomar-registry.org/) requires it of every submission. Part of the [Mathlib Initiative](https://mathlib-initiative.org/)'s [Formal Frontier](https://mathlib-initiative.org/formal-frontier/) programme. |
| [`leanprover-community/intentions`](https://github.com/leanprover-community/intentions), [`leanprover-community/project-intentions`](https://github.com/leanprover-community/project-intentions) | Intention registration: a public board of who is formalizing what. [Tau Ceti](https://github.com/TauCetiProject/TauCeti) respects registered intentions when choosing roadmap material. Check it before starting a formalization, so two people do not prove the same theorem twice. |
| [`Vilin97/lean-pool`](https://github.com/Vilin97/lean-pool) | Lean Pool: an arXiv-like archive of independent Lean 4 formalizations outside Mathlib's scope, kept `sorry`-free and pinned to current Mathlib by linters and LLM review. One Lake dependency imports every pooled project (173 as of 2026-09-09, from group theory and Lie theory to analytic number theory and probability), each with a provenance label (`human`, `AI`, `mix`). `LeanPool/projects.yml` is the machine-readable catalogue: query it by `branch` before any GitHub search, and prefer importing the pooled copy over a dormant upstream repository. Rows marked *(in Lean Pool)* in the tables above are already pooled. |
| [`merely-true/merely-true`](https://github.com/merely-true/merely-true) | Permissive shared repository of AI-generated Lean mathematics with CI-only review (no `sorry`, no axioms). Statement bank of last resort; check declarations before reuse, as with `atlas-lean`. |

## Textbook companions and worked proof corpora

| Source | Content |
| --- | --- |
| [`leanprover-community/mathematics_in_lean`](https://github.com/leanprover-community/mathematics_in_lean) | *Mathematics in Lean* tutorial. |
| [`hrmacbeth/math2001`](https://github.com/hrmacbeth/math2001) | Proof-writing course, paper and Lean. |
| [`djvelleman/HTPILeanPackage`](https://github.com/djvelleman/HTPILeanPackage) | *How To Prove It* companion. |
| [`PatrickMassot/GlimpseOfLean`](https://github.com/PatrickMassot/GlimpseOfLean) | Fast introduction to theorem proving. |
| [`leanprover-community/NNG4`](https://github.com/leanprover-community/NNG4) | Natural Number Game. |

## Core libraries and infrastructure

| Source | Content |
| --- | --- |
| [`leanprover-community/mathlib4`](https://github.com/leanprover-community/mathlib4) | Large formal mathematics library covering algebra, number theory, topology, analysis, measure theory, geometry, combinatorics, and many other subjects. |
| [`leanprover-community/batteries`](https://github.com/leanprover-community/batteries) | Extended standard library. |
| [`leanprover-community/aesop`](https://github.com/leanprover-community/aesop) | White-box proof automation. |
| [`leanprover-community/duper`](https://github.com/leanprover-community/duper), [`leanprover-community/lean-auto`](https://github.com/leanprover-community/lean-auto) | Automated theorem proving in Lean. |
| [`leanprover-community/plausible`](https://github.com/leanprover-community/plausible) | Property-based counterexample search. |
| [`leanprover-community/repl`](https://github.com/leanprover-community/repl) | Programmatic proof checking. |
| [`PatrickMassot/leanblueprint`](https://github.com/PatrickMassot/leanblueprint) | Formalization blueprint infrastructure. |
| [`siddhartha-gadgil/LeanAide`](https://github.com/siddhartha-gadgil/LeanAide) | AI aids for autoformalization. |

## Rocq and Agda

| Source | Content |
| --- | --- |
| [`rocq-prover/rocq`](https://github.com/rocq-prover/rocq) | Rocq core library: elementary logic, basic data types, equality, arithmetic foundations, and well-founded recursion. |
| [`rocq-prover/stdlib`](https://github.com/rocq-prover/stdlib) | Rocq standard mathematical library: sets, lists, sorting, arithmetic, numbers, relations, and general-purpose definitions and theorems. |
| [`UniMath/UniMath`](https://github.com/UniMath/UniMath) | Univalent mathematics in Rocq/Coq; large formal category-theory corpus. |
| [`HoTT/Coq-HoTT`](https://github.com/HoTT/Coq-HoTT) | Homotopy type theory in Rocq/Coq. |
| [`inQWIRE/QuantumLib`](https://github.com/inQWIRE/QuantumLib) | Reusable quantum-computing mathematics in Rocq/Coq: complex matrices, finite groups, subspaces, permutations, measurement and quantum operations. |
| [`math-comp/math-comp`](https://github.com/math-comp/math-comp) | Mathematical Components: finite structures, algebra, finite group theory, field theory, matrices, and polynomials. |
| [`math-comp/analysis`](https://github.com/math-comp/analysis) | Real and classical analysis over Mathematical Components: topology, measure/integration, real numbers, sequences, and distributions. |
| [`math-comp/odd-order`](https://github.com/math-comp/odd-order) | Feit–Thompson Odd Order Theorem and the supporting finite-group theory developed for its proof. |
| [`rocq-community/fourcolor`](https://github.com/rocq-community/fourcolor) | Four Color Theorem, including the graph theory and real analysis needed for the proof. |
| [`rocq-community/corn`](https://github.com/rocq-community/corn) | Constructive mathematics library in Rocq/Coq. |
| [`GeoCoq/GeoCoq`](https://github.com/GeoCoq/GeoCoq) | Synthetic geometry from Tarski-style axioms, with Euclidean, Hilbert, parallel-postulate, and algebraic geometry developments. |
| [`AbsInt/CompCert`](https://github.com/AbsInt/CompCert) | Formal definitions of C and assembly semantics, memory models and compiler passes, plus the correctness proofs of CompCert. |
| [`iris/iris`](https://gitlab.mpi-sws.org/iris/iris) | Iris higher-order concurrent separation logic and program logic, including ghost-state constructions and proof automation. |
| [`iris/stdpp`](https://gitlab.mpi-sws.org/iris/stdpp) | General-purpose Rocq definitions for data structures, finite maps, and algebra, used by Iris and independently reusable. |
| [`thery/coqprime`](https://github.com/thery/coqprime) | Number theory, elliptic curves, modular arithmetic, and primality certification. |
| [`jwiegley/category-theory`](https://github.com/jwiegley/category-theory) | Large axiom-free category-theory development: categories, functors, adjunctions, (co)limits, Kan constructions, monads/comonads and related structures. |
| [`uwplse/verdi`](https://github.com/uwplse/verdi) | Formal models and proofs for distributed systems, including reusable definitions for verified distributed algorithms. |
| [`IBM/FormalML`](https://github.com/IBM/FormalML) | General probability in Rocq/Coq, including sigma-algebras, expectation, conditional expectation and martingales, with applications to stochastic approximation and reinforcement learning. |
| [`formal-land/rocq-of-rust`](https://github.com/formal-land/rocq-of-rust) | Formal definitions of Rust types, traits, integer operations, and control flow in Rocq, used to verify Rust programs. |
| [`thery/Selinger`](https://github.com/thery/Selinger) | Laurent Théry's formalization of Selinger's quantum-gate synthesis proof, combining number-theoretic and linear-algebraic definitions over Mathematical Components. |
| [`agda/agda-stdlib`](https://github.com/agda/agda-stdlib) | Agda standard library: algebraic structures, orders, relations, finite structures, and data types. |
| [`UniMath/agda-unimath`](https://github.com/UniMath/agda-unimath) | Univalent mathematics in Agda, including extensive category theory. |
| [`agda/cubical`](https://github.com/agda/cubical) | Cubical type theory, homotopy type theory, and related mathematics in Agda. |
| [`agda/agda-categories`](https://github.com/agda/agda-categories) | Category theory in Agda: limits, adjunctions, monoidal/enriched and higher categorical structures, fibrations and topoi. |
| [`the1lab/1lab`](https://github.com/the1lab/1lab) | Cross-linked HoTT reference in cubical Agda. |
| [`martinescardo/TypeTopology`](https://github.com/martinescardo/TypeTopology) | Topology and logic from the univalent point of view, in Agda. |
| [`HoTT-Intro/Agda`](https://github.com/HoTT-Intro/Agda) | Section-by-section Agda formalization of Rijke's *Introduction to Homotopy Type Theory*. |
| [`Sterling1111/rocq-spivak`](https://github.com/Sterling1111/rocq-spivak) | Rocq real-analysis development following Spivak, including formal sets, limits, derivatives, continuity, and chapter-level theorem statements. |
| [`thealgebraist/zeta-two-thirds-coq`](https://github.com/thealgebraist/zeta-two-thirds-coq) | Rocq formalization of the two-thirds simple-zero result for the Riemann zeta function, including finite-sum and rank/trace statements. |
| [`takanuva/cps`](https://github.com/takanuva/cps) | Rocq formalization of continuation-passing calculi with syntax, substitution metatheory, categorical models, and term/presheaf constructions. |
| [`code-artifacts/taps-plume-coq`](https://github.com/code-artifacts/taps-plume-coq) | Rocq formalization of transactional access patterns from Plume, including operation/transaction histories and consistency relations. |
| [`alonjon-sysfeat/SysFEAT-Agda`](https://github.com/alonjon-sysfeat/SysFEAT-Agda) | Agda formalization of the SysFEAT ontology and relation calculus with bounded-individual classes, subtype witnesses, and linkage constructions. |
| [`slemus9/hott-intro`](https://github.com/slemus9/hott-intro) | Agda development following Rijke's homotopy type theory text, including dependent sums, coproducts, finite types, decidability, and identification types. |
| [`SkyLabsAI/BRiCk`](https://github.com/SkyLabsAI/BRiCk) | Rocq formalization of C++ syntax and semantics, including ABI-sensitive integral promotion, typed values, translation units, and semantic preservation lemmas. |
| [`harp-project/Core-Erlang-Formalization`](https://github.com/harp-project/Core-Erlang-Formalization) | Rocq formalization of Core Erlang with sequential and concurrent semantics, maps, built-in functions, scoping, closure, and program-equivalence infrastructure. |
| [`HFunction2013/basel-coq-proof`](https://github.com/HFunction2013/basel-coq-proof) | Rocq development of the Basel-series proof with reusable finite-sum and analytic definitions. |
| [`gangchensh/micpro-riscv-3`](https://github.com/gangchensh/micpro-riscv-3) | Rocq formalization of a three-stage RISC-V processor, including bit-level encodings, core semantics, and machine-correctness lemmas. |
| [`chaikens/IntroDepTypeThProofAssts`](https://github.com/chaikens/IntroDepTypeThProofAssts) | Rocq dependent-type and theorem-proving examples with explicit definitions and proof terms. |
| [`leibniz-stt/agda-formalization`](https://github.com/leibniz-stt/agda-formalization) | Agda formalization of Leibniz constructions and simplicial type theory, including category-theoretic and wild-preorder interfaces. |

## Isabelle and HOL

| Source | Content |
| --- | --- |
| [`isabelle-prover/mirror-isabelle`](https://github.com/isabelle-prover/mirror-isabelle) | Isabelle/HOL libraries covering logic, sets, algebra, analysis, topology, number theory, probability, and foundational theories. |
| [`isabelle-prover/mirror-afp-devel`](https://github.com/isabelle-prover/mirror-afp-devel) | Archive of Formal Proofs (AFP): a large Isabelle library spanning pure mathematics, algorithms, semantics, verification, and scientific applications. |
| [`seL4/l4v`](https://github.com/seL4/l4v) | Isabelle/HOL formal specifications and proofs for seL4, with reusable theories for machine words, state monads, separation logic, refinement, and program verification. |
| [`jrh13/hol-light`](https://github.com/jrh13/hol-light) | HOL Light and its mathematical library: analysis, topology, geometry, algebra, number theory, and related foundational material. |
| [`flyspeck/flyspeck`](https://github.com/flyspeck/flyspeck) | HOL Light formalization of the Kepler conjecture, together with the supporting geometry and analysis. |
| [`HOL-Theorem-Prover/HOL`](https://github.com/HOL-Theorem-Prover/HOL) | HOL4 libraries covering higher-order logic, algebra, analysis, semantics, and large formal developments. |
| [`CakeML/cakeml`](https://github.com/CakeML/cakeml) | HOL4 definitions of CakeML syntax and semantics, compiler/intermediate languages, type systems and the verified compiler proofs. |
| [`CakeML/candle`](https://github.com/CakeML/candle) | Formal definitions and proofs for Candle, a verified implementation of HOL Light developed within CakeML. |
| [`HOLMS-lib/HOLMS`](https://github.com/HOLMS-lib/HOLMS) | HOL Light Library for Modal Systems: Kripke semantics, normal modal logics, labelled calculi, completeness and verified proof search. |
| [`kth-step/HOL4P4`](https://github.com/kth-step/HOL4P4) | HOL4 formal syntax, small-step semantics, type system, architecture models and symbolic execution for the P4 language. |
| [`CakeML/game-of-life`](https://github.com/CakeML/game-of-life) | HOL4 formalization of Conway's Game of Life and verified compilation into Life circuits, including executable semantics and circuit definitions. |
| [`NatLabRockies/BdL`](https://github.com/NatLabRockies/BdL) | Isabelle/HOL differential dynamic logic for biological dynamical systems, including ODE rules, differential invariants, and stability arguments. |
| [`nisizaki/penv-confluence-WCTP`](https://github.com/nisizaki/penv-confluence-WCTP) | Isabelle/HOL LambdaEnv/LambdaPEnv reduction systems and confluence, with explicit syntax, reduction relations, termination, and local-confluence lemmas. |
| [`nisizaki/frenv-confluence-WCTP`](https://github.com/nisizaki/frenv-confluence-WCTP) | Isabelle/HOL FREnv/EnvEps confluence development with a companion Lean formalization of the term and reduction interfaces. |
| [`ajreynol/iogos`](https://github.com/ajreynol/iogos) | Isabelle formalization containing CPC specifications and obligation/semantics infrastructure. |
| [`stepanholub/ZFfin-formalization`](https://github.com/stepanholub/ZFfin-formalization) | Isabelle set-theory development using permutation models to separate finite fragments of ZF-style axiom systems, including regularity and transitive-superset arguments. |
| [`catalin-carstea/arxiv-2606.15977-formalization`](https://github.com/catalin-carstea/arxiv-2606.15977-formalization) | Isabelle development for flat-cell recovery and related inverse-problem arguments, with affine-hyperplane arrangements, dimension propagation, and literature-interface locales. |

## Mizar, Metamath, ACL2, PVS, Twelf

| Source | Content |
| --- | --- |
| [Current Mizar Mathematical Library](https://mizar.uwb.edu.pl/version/current/mml/) | Mizar Mathematical Library: a centrally maintained collection of formal definitions and proofs across mainstream mathematics. It is synchronized directly from the current Mizar distribution because the public `MizarSystem/MML` GitHub repository is an old 2012 snapshot. |
| [`metamath/set.mm`](https://github.com/metamath/set.mm) | Metamath Proof Explorer and companion databases: ZFC mathematics plus intuitionistic set theory, NF, higher-order and quantum logic databases. |
| [`digama0/mm0`](https://github.com/digama0/mm0) | Metamath Zero/One formal specifications and examples, including arithmetic and metatheory. |
| [`acl2/acl2`](https://github.com/acl2/acl2) | ACL2 Community Books: arithmetic, algebra, data structures, formal models of hardware and software, verified algorithms, and reusable definitions. |
| [`nasa/pvslib`](https://github.com/nasa/pvslib) | NASALib: PVS formalizations spanning algebra, analysis, geometry, numerical methods, decision procedures, and applications. |
| [`SRI-CSL/PVS`](https://github.com/SRI-CSL/PVS) | PVS and its standard libraries, including the formal definitions used by NASALib. |
| [`standardml/twelf`](https://github.com/standardml/twelf) | Twelf/LF examples and case studies: lambda calculi, Cartesian closed categories, Church–Rosser, cut elimination, Mini-ML, logic programming and metatheory. |
