# Formalization source annotations

[`sources.tsv`](./sources.tsv) is the canonical inventory of formalization
sources. This document is a human annotation layer: mathematical subject guides,
notes about notable source contents, and external search/discovery surfaces. It
may mention only a useful subset of the 909 indexed sources and must never be
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
| [`CBirkbeck/WeilConverse`](https://github.com/CBirkbeck/WeilConverse) | Weil converse theorem. |
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
| [`mrdouglasny/OSforGFF`](https://github.com/mrdouglasny/OSforGFF) | Gaussian free field in d=4 and the Osterwalder–Schrader axioms. Same author: [`gaussian-field`](https://github.com/mrdouglasny/gaussian-field), [`lgt`](https://github.com/mrdouglasny/lgt) (lattice gauge theory), [`pphi2`](https://github.com/mrdouglasny/pphi2) (φ⁴₂ construction), [`seiberg-witten`](https://github.com/mrdouglasny/seiberg-witten), [`hille-yosida`](https://github.com/mrdouglasny/hille-yosida), [`markov-semigroups`](https://github.com/mrdouglasny/markov-semigroups), [`spectral-positivity`](https://github.com/mrdouglasny/spectral-positivity) (Perron–Frobenius, Jentzsch). |
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
