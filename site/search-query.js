(function (root, factory) {
	const api = factory();
	if (typeof module === "object" && module.exports) module.exports = api;
	root.FormalizationSearchQuery = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
	function rx(text) {
		return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
	}

	function quotedPattern(pattern) {
		return `"${pattern.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
	}

	function normalizedQueryTerms(text, config) {
		const stopwords = new Set(config.stopwords || []);
		const proofAssistantTerms = config.proof_assistant_terms || {};
		const words = text.match(/[\p{L}\p{N}_⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉ℚℤℝℂ∞+-]+/gu) || [];
		const terms = [];
		let proofFilter = null;
		for (const word of words) {
			const lower = word.toLocaleLowerCase();
			if (Object.hasOwn(proofAssistantTerms, lower)) {
				proofFilter = proofAssistantTerms[lower];
				continue;
			}
			if (!stopwords.has(lower)) terms.push(word);
		}
		return {terms, proofFilter};
	}

	return {rx, quotedPattern, normalizedQueryTerms};
});
