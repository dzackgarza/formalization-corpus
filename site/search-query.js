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

	function stripIntentPrefix(text, config) {
		const trimmed = text.trim();
		const lower = trimmed.toLocaleLowerCase();
		const prefixes = [...(config.intent_prefixes || [])].sort((a, b) => b.length - a.length);
		for (const rawPrefix of prefixes) {
			const prefix = rawPrefix.toLocaleLowerCase();
			if (lower === prefix) return "";
			if (lower.startsWith(`${prefix} `)) return trimmed.slice(rawPrefix.length).trim();
		}
		return trimmed;
	}

	function normalizedQueryTerms(text, config) {
		const stopwords = new Set(config.stopwords || []);
		const proofAssistantTerms = config.proof_assistant_terms || {};
		const normalized = stripIntentPrefix(text, config);
		const words = normalized.match(/[\p{L}\p{N}_⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉ℚℤℝℂ∞+-]+/gu) || [];
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

	return {rx, quotedPattern, stripIntentPrefix, normalizedQueryTerms};
});
