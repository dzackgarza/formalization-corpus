;; Deterministic Lean declaration/signature evidence. Capture parser-owned
;; declaration metadata and immediate member signatures, never proof bodies.

(theorem name: (_) @declaration_name)
(theorem (binders) @declaration_binders)
(theorem type: (_) @declaration_type)

(def name: (_) @declaration_name)
(def (binders) @declaration_binders)
(def type: (_) @declaration_type)

(abbrev name: (_) @declaration_name)
(abbrev (binders) @declaration_binders)
(abbrev type: (_) @declaration_type)

(opaque name: (_) @declaration_name)
(opaque (binders) @declaration_binders)
(opaque type: (_) @declaration_type)

(axiom name: (_) @declaration_name)
(axiom (binders) @declaration_binders)
(axiom type: (_) @declaration_type)

(structure name: (_) @declaration_name)
(structure (binders) @declaration_binders)
(field name: (_) @member_name)
(field type: (_) @member_type)

(inductive name: (_) @declaration_name)
(inductive (binders) @declaration_binders)
(ctor_alt name: (_) @member_name)
(ctor_alt type: (_) @member_type)

(instance name: (_) @declaration_name)
(instance type: (_) @declaration_type)
(example type: (_) @declaration_type)
