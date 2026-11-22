"""Offline verification of the exact retrieval-only patch artifact, not Go acceptance.

Sparse predecessor excerpts come from the pinned source after patch 0001. Full
pre/post image hashes are build-admission evidence, not hashes of these sparse
fixtures. Tencent MIT notice is retained in the companion patch manifest.
"""

import hashlib
import json
import logging
import re
import shutil
import subprocess
from pathlib import Path

import pytest

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
PATCH_ROOT = ROOT / "deploy/weknora/patches"
FROZEN_PREDECESSOR = json.loads(
    '{"internal/application/service/extract.go": {"line_count": 951, "regions": [[162, "// enqueueDataTableSummaryIfNeeded enqueues table summary work for spreadsheet\\n// imports. fileName is a fallback for older records whose FileType is empty.\\nfunc enqueueDataTableSummaryIfNeeded(\\n\\tctx context.Context,\\n\\tclient interfaces.TaskEnqueuer,\\n\\ttenantID uint64,\\n\\tknowledgeID string,\\n\\tfileName, fileType, summaryModelID, embeddingModelID string,\\n\\tprocessOverrides *types.KnowledgeProcessOverrides,\\n) {\\n\\t// The document-summary opt-out also covers the independent table-summary task.\\n\\t// A nil override or omitted switch keeps the upstream default enabled.\\n\\tif processOverrides != nil && processOverrides.SummaryEnabled != nil && !*processOverrides.SummaryEnabled {\\n\\t\\tlogger.Infof(ctx, \\"Skipping data table summary for knowledge %s: summary explicitly disabled\\", knowledgeID)\\n\\t\\treturn\\n\\t}\\n\\tft := normalizeFileExtension(fileType)\\n\\tif ft == \\"\\" && fileName != \\"\\" {\\n\\t\\tft = getFileType(fileName)\\n\\t}\\n"]]}, "internal/application/service/knowledge_post_process.go": {"line_count": 741, "regions": [[209, "\\t//    per-knowledge op, and the batch worker calls FinalizeSubtask once\\n\\t//    when that op reaches a terminal state (mapped successfully or\\n\\t//    dead-lettered after exhausting retries). Counting it keeps the row\\n\\t//    in \\"finalizing\\" — i.e. shown as in-progress and still cancellable —\\n\\t//    until wiki generation actually finishes instead of flipping to\\n\\t//    completed while wiki runs minutes later. A wiki op that never\\n\\t//    drains is bounded by the housekeeping finalizing sweep.\\n\\twillSpawnSummary := eff.SummaryEnabled && len(textChunks) > 0\\n\\twillSpawnQuestion := len(textChunks) > 0 && kb.NeedsEmbeddingModel() &&\\n\\t\\teff.QuestionGenerationConfig.Enabled\\n\\twillSpawnWiki := kb.IndexingStrategy.WikiEnabled && len(textChunks) > 0\\n\\twillSpawnAutoTag := kb.Type == types.KnowledgeBaseTypeDocument &&\\n\\t\\tkb.AutoTagConfig != nil && kb.AutoTagConfig.Enabled && len(textChunks) > 0\\n\\tenqueuedAutoTag := false\\n\\n\\t// Question generation now fans out one subtask per plain text chunk\\n\\t// (mirroring the graph-extract per-chunk pattern) so each chunk\'s LLM\\n\\t// call retries / cancels / traces independently. We only target\\n\\t// ChunkTypeText here — OCR / Caption chunks were never fed to question\\n\\t// generation in the legacy whole-knowledge loop, so excluding them\\n\\t// keeps behavior identical. Link-only text chunks (scanned PDF pages)\\n\\t// are skipped: the LLM has nothing to ask about and tends to echo the\\n"], [262, "\\t}\\n\\texpectedSubtasks += graphChunkCount\\n\\n\\t// enteredFinalizing is set only when the processing-to-finalizing handoff\\n\\t// actually seeded the counter. For Wiki-enabled knowledge, that handoff\\n\\t// also persists the pending Wiki op in the same transaction.\\n\\tenteredFinalizing := false\\n\\twikiSlotOwned := false\\n\\n\\tswitch {\\n\\tcase knowledge.ParseStatus == types.ParseStatusFinalizing && kb.IndexingStrategy.WikiEnabled:\\n\\t\\t// A previous delivery may have persisted the Wiki op but failed to\\n\\t\\t// enqueue its KB-scoped trigger. Retry only the trigger: appending a\\n\\t\\t// second pending op would duplicate durable work and its finalizer.\\n\\t\\tif err := enqueueWikiIngestTrigger(ctx, s.taskEnqueuer, payload.TenantID, payload.KnowledgeBaseID); err != nil {\\n\\t\\t\\ts.tracker().FailSpanRetryable(ctx, postSpan, \\"WIKI_TRIGGER_ENQUEUE_FAILED\\", err.Error(), err)\\n\\t\\t\\treturn fmt.Errorf(\\"retry wiki ingest trigger: %w\\", err)\\n\\t\\t}\\n\\t\\tlogger.Infof(ctx, \\"[KnowledgePostProcess] Re-enqueued wiki ingest trigger for %s\\", payload.KnowledgeID)\\n\\t\\tretryOutput := types.JSONMap{\\"retried_wiki_trigger\\": true}\\n\\t\\ts.tracker().EndSpan(ctx, postSpan, retryOutput)\\n"]]}, "internal/application/service/knowledge_process.go": {"line_count": 4890, "regions": [[400, "\\n// processChunks processes chunks and creates embeddings for knowledge content\\nfunc (s *knowledgeService) processChunks(ctx context.Context,\\n\\tkb *types.KnowledgeBase, knowledge *types.Knowledge, chunks []types.ParsedChunk,\\n\\topts ...ProcessChunksOptions,\\n) error {\\n\\t// Get options\\n\\tvar options ProcessChunksOptions\\n\\tif len(opts) > 0 {\\n\\t\\toptions = opts[0]\\n\\t}\\n\\n\\t// Parser output and manually supplied passages can contain malformed byte\\n\\t// sequences. Clean them before logging, chunk persistence, or embedding;\\n\\t// the embedding provider and tracing/database drivers expect valid UTF-8.\\n\\tfor i := range chunks {\\n\\t\\tchunks[i].Content = common.CleanInvalidUTF8(chunks[i].Content)\\n\\t\\tchunks[i].ContextHeader = common.CleanInvalidUTF8(chunks[i].ContextHeader)\\n\\t\\tfor j := range chunks[i].Images {\\n\\t\\t\\tchunks[i].Images[j].URL = common.CleanInvalidUTF8(chunks[i].Images[j].URL)\\n"], [4333, "\\t}\\n\\ts.beginStage(ctx, knowledge.ID, types.StageDocReader, docInput)\\n\\tisURL := payload.URL != \\"\\"\\n\\tfileType := payload.FileType\\n\\ttenantOverrides := s.getParserEngineOverridesFromContext(ctx)\\n\\tvar uploadOverrides map[string]string\\n\\tif processOverrides, err := knowledge.ProcessOverrides(); err == nil && processOverrides != nil {\\n\\t\\tuploadOverrides = processOverrides.ParserEngineOverrides\\n\\t}\\n\\tmergedOverrides := MergeParserEngineOverrides(tenantOverrides, uploadOverrides)\\n\\tapplyParserRuleOverrides(mergedOverrides, eff.ChunkingConfig, fileType)\\n\\tif err := validateParserEngineOverrideURLs(mergedOverrides); err != nil {\\n\\t\\tlogger.Errorf(ctx, \\"Parser endpoint rejected for SSRF protection: %v\\", err)\\n\\t\\tknowledge.ParseStatus = \\"failed\\"\\n\\t\\tknowledge.ErrorMessage = \\"Parser endpoint is not allowed for security reasons\\"\\n\\t\\tknowledge.UpdatedAt = time.Now()\\n\\t\\ts.repo.UpdateKnowledge(ctx, knowledge)\\n\\t\\ts.failStage(ctx, knowledge.ID, types.StageDocReader,\\n\\t\\t\\twerrors.ErrCodeDocReaderParseFailed, knowledge.ErrorMessage, err)\\n\\t\\treturn nil, nil\\n"], [4366, "\\t}\\n\\n\\tparserEngine := eff.ChunkingConfig.ResolveParserEngine(fileType)\\n\\tif isURL {\\n\\t\\tparserEngine = eff.ChunkingConfig.ResolveParserEngine(\\"url\\")\\n\\t}\\n\\n\\tlogger.Infof(ctx, \\"[convert] kb=%s fileType=%s isURL=%v engine=%q rules=%+v\\",\\n\\t\\tkb.ID, fileType, isURL, parserEngine, eff.ChunkingConfig.ParserEngineRules)\\n\\n\\tvar reader interfaces.DocReader = s.resolveDocReader(ctx, parserEngine, fileType, isURL, mergedOverrides)\\n\\tif reader == nil {\\n\\t\\tlogger.Errorf(ctx, \\"[convert] no doc reader for kb=%s knowledge=%s fileType=%s engine=%q isURL=%v\\",\\n\\t\\t\\tkb.ID, knowledge.ID, fileType, parserEngine, isURL)\\n\\t\\tknowledge.ParseStatus = \\"failed\\"\\n\\t\\tknowledge.ErrorMessage = \\"Document parsing service is not configured. Please use text/paragraph import or set DOCREADER_ADDR.\\"\\n\\t\\tknowledge.UpdatedAt = time.Now()\\n\\t\\ts.repo.UpdateKnowledge(ctx, knowledge)\\n\\t\\ts.failStage(ctx, knowledge.ID, types.StageDocReader,\\n\\t\\t\\twerrors.ErrCodeDocReaderUnavailable, knowledge.ErrorMessage, nil)\\n"], [4558, "// processing. It returns an error only when no path is left to move the\\n// knowledge out of \\"processing\\" (see releaseUnownedMultimodalSlots).\\nfunc (s *knowledgeService) enqueueImageMultimodalTasks(\\n\\tctx context.Context,\\n\\tknowledge *types.Knowledge,\\n\\tkb *types.KnowledgeBase,\\n\\timages []docparser.StoredImage,\\n\\tchunks []types.ParsedChunk,\\n\\tmetadata map[string]string,\\n) error {\\n\\tif s.task == nil || len(images) == 0 {\\n\\t\\treturn nil\\n\\t}\\n\\n\\tattempt := attemptFromCtx(ctx)\\n\\tlang := types.LanguageFromContextOrDefault(ctx)\\n\\tredisKey := multimodalPendingKey(knowledge.ID)\\n\\t// The counter has to be seeded BEFORE the first task is enqueued: an image\\n\\t// task that finishes early would otherwise decrement a key we are about to\\n\\t// overwrite, and its slot would be counted twice. The cost of seeding\\n\\t// first is that a slot whose task never reaches the queue has no owner to\\n"]]}, "internal/application/service/knowledge_process_config.go": {"line_count": 380, "regions": [[30, "\\t\\treturn\\n\\t}\\n\\toverrides[xlsxFirstRowAsHeaderOverride] = strconv.FormatBool(*rule.XLSXFirstRowAsHeader)\\n}\\n\\nfunc normalizeParserFileType(fileType string) string {\\n\\treturn strings.TrimPrefix(strings.ToLower(strings.TrimSpace(fileType)), \\".\\")\\n}\\n\\n// ResolveProcessConfig merges KB defaults with per-upload overrides for the parse pipeline.\\nfunc ResolveProcessConfig(kb *types.KnowledgeBase, overrides *types.KnowledgeProcessOverrides) types.EffectiveProcessConfig {\\n\\timageCfg := kb.ImageProcessingConfig\\n\\teff := types.EffectiveProcessConfig{\\n\\t\\tSummaryEnabled:           true,\\n\\t\\tChunkingConfig:           kb.ChunkingConfig,\\n\\t\\tEnableMultimodel:         kb.IsMultimodalEnabled(),\\n\\t\\tVLMConfig:                kb.VLMConfig,\\n\\t\\tASRConfig:                kb.ASRConfig,\\n\\t\\tQuestionGenerationConfig: defaultQuestionGenerationConfig(kb),\\n\\t\\tGraphEnabled:             kb.IsGraphEnabled(),\\n\\t\\tExtractConfig:            derefExtractConfig(kb.ExtractConfig),\\n\\t\\tImageAttrsEnabled:        imageCfg.ImageAttrsEnabled,\\n\\t\\tImageVectorEnabled:       imageCfg.ImageVectorEnabled,\\n"], [172, "\\tkb *types.KnowledgeBase,\\n\\tfileType string,\\n\\tprocessOverrides *types.KnowledgeProcessOverrides,\\n\\tenableMultimodel *bool,\\n) (types.EffectiveProcessConfig, error) {\\n\\tif err := validateImportFileType(fileType); err != nil {\\n\\t\\treturn types.EffectiveProcessConfig{}, err\\n\\t}\\n\\n\\teff := ResolveProcessConfig(kb, processOverrides)\\n\\tif enableMultimodel != nil && (processOverrides == nil || processOverrides.EnableMultimodel == nil) {\\n\\t\\teff.EnableMultimodel = *enableMultimodel\\n\\t}\\n\\n\\tif processOverrides != nil {\\n\\t\\tif err := validateEffectiveProcessOverrides(eff, []string{fileType}); err != nil {\\n\\t\\t\\treturn eff, err\\n\\t\\t}\\n\\t} else if err := validateDefaultFileImportRequirements(ctx, kb, eff, fileType); err != nil {\\n\\t\\treturn eff, err\\n\\t}\\n"], [247, "// knowledge record, and returns the effective config for task enqueue.\\nfunc ApplyKnowledgeProcessOverrides(\\n\\tctx context.Context,\\n\\tkb *types.KnowledgeBase,\\n\\tknowledge *types.Knowledge,\\n\\tprocessOverrides *types.KnowledgeProcessOverrides,\\n\\tfileTypes []string,\\n\\tenableMultimodel *bool,\\n) (types.EffectiveProcessConfig, error) {\\n\\teff := ResolveProcessConfig(kb, processOverrides)\\n\\tif enableMultimodel != nil && (processOverrides == nil || processOverrides.EnableMultimodel == nil) {\\n\\t\\teff.EnableMultimodel = *enableMultimodel\\n\\t}\\n\\tif processOverrides == nil {\\n\\t\\treturn eff, nil\\n\\t}\\n\\tif err := validateEffectiveProcessOverrides(eff, fileTypes); err != nil {\\n\\t\\treturn eff, err\\n\\t}\\n\\tif err := knowledge.SetProcessOverrides(processOverrides); err != nil {\\n\\t\\treturn eff, err\\n"]]}, "internal/application/service/knowledgebase.go": {"line_count": 1666, "regions": [[129, "\\n// CreateKnowledgeBase creates a new knowledge base.\\n//\\n// When VectorStoreID is set, the binding is validated against the caller\'s\\n// tenant scope and the engine registry before persisting. A nil or\\n// empty-string VectorStoreID is normalized to nil (\\"use the tenant\'s\\n// effective engines\\") to match the retrieve-engine factory\'s pre-condition.\\nfunc (s *knowledgeBaseService) CreateKnowledgeBase(ctx context.Context,\\n\\tkb *types.KnowledgeBase,\\n) (*types.KnowledgeBase, error) {\\n\\t// Generate UUID and set creation timestamps\\n\\tif kb.ID == \\"\\" {\\n\\t\\tkb.ID = uuid.New().String()\\n\\t}\\n\\tkb.CreatedAt = time.Now()\\n\\tkb.TenantID = types.MustTenantIDFromContext(ctx)\\n\\tkb.UpdatedAt = time.Now()\\n\\t// Record the creator so RBAC\'s RequireOwnershipOrRole can let\\n\\t// Contributors edit their own KBs without granting them tenant-wide\\n\\t// edit rights. The X-API-Key auth path attaches a synthetic\\n"]]}, "internal/application/service/knowledgebase_profile.go": {"line_count": 480, "regions": [[114, "// requestKnowledgeBaseProfileRefresh enqueues a debounced rebuild. It is a\\n// package-level helper so the summary, post-process and delete paths can call\\n// it with the enqueuer they already hold, without a new dependency. Failures\\n// are logged, never returned: a missing description must not fail ingestion.\\nfunc requestKnowledgeBaseProfileRefresh(\\n\\tctx context.Context,\\n\\tenqueuer interfaces.TaskEnqueuer,\\n\\tkb *types.KnowledgeBase,\\n\\tforce bool,\\n) error {\\n\\tif enqueuer == nil || !knowledgeBaseProfileEligible(kb) {\\n\\t\\treturn nil\\n\\t}\\n\\tif !force && !kb.ProfileConfig.IsEnabled() {\\n\\t\\treturn nil\\n\\t}\\n\\tpayload := types.KnowledgeBaseProfilePayload{\\n\\t\\tTenantID:        kb.TenantID,\\n\\t\\tKnowledgeBaseID: kb.ID,\\n\\t\\tLanguage:        types.LanguageFromContextOrDefault(ctx),\\n\\t\\tForce:           force,\\n"], [212, "\\t\\t}\\n\\t\\treturn err\\n\\t}\\n\\treturn nil\\n}\\n\\n// BuildAggregate implements interfaces.KnowledgeBaseProfileService.\\nfunc (s *KnowledgeBaseProfileService) BuildAggregate(\\n\\tctx context.Context, kb *types.KnowledgeBase,\\n) (*types.KnowledgeBaseProfileAggregate, error) {\\n\\tif !knowledgeBaseProfileEligible(kb) {\\n\\t\\treturn nil, ErrKnowledgeBaseProfileUnsupported\\n\\t}\\n\\trows, err := s.knowledgeRepo.ListKnowledgeProfileRows(ctx, kb.TenantID, kb.ID)\\n\\tif err != nil {\\n\\t\\treturn nil, fmt.Errorf(\\"list knowledge profile rows: %w\\", err)\\n\\t}\\n\\tif err := s.attachTags(ctx, rows); err != nil {\\n\\t\\treturn nil, err\\n\\t}\\n\\treturn types.BuildKnowledgeBaseProfileAggregate(rows), nil\\n"], [270, "\\t\\t\\trow.Tags = names\\n\\t\\t}\\n\\t}\\n\\treturn nil\\n}\\n\\n// GenerateKnowledgeBaseProfile implements interfaces.KnowledgeBaseProfileService.\\nfunc (s *KnowledgeBaseProfileService) GenerateKnowledgeBaseProfile(\\n\\tctx context.Context, kb *types.KnowledgeBase, force bool,\\n) (*types.KnowledgeBaseProfile, error) {\\n\\tif !knowledgeBaseProfileEligible(kb) {\\n\\t\\treturn nil, ErrKnowledgeBaseProfileUnsupported\\n\\t}\\n\\tagg, err := s.BuildAggregate(ctx, kb)\\n\\tif err != nil {\\n\\t\\treturn nil, err\\n\\t}\\n\\tnow := time.Now()\\n\\texisting := kb.GeneratedProfile\\n\\n\\tif agg.IsEmpty() {\\n"]]}, "internal/application/service/knowledgebase_search_rerank.go": {"line_count": 236, "regions": [[58, "// it, reranks the fused candidates before cutting to the requested count.\\n//\\n// The rerank candidate pool is the top max(top_k, DefaultRetrievalTopK)\\n// fused chunks, so a small match_count still gives the model a meaningful\\n// pool to choose from. Context enrichment (parent / nearby / relation\\n// chunks) runs on the reranked rows only.\\nfunc (s *knowledgeBaseService) HybridSearchWithRerank(ctx context.Context,\\n\\tid string,\\n\\tparams types.SearchParams,\\n) (*types.RetrievalResult, error) {\\n\\tif !params.Rerank.IsEnabled() {\\n\\t\\tresults, err := s.HybridSearch(ctx, id, params)\\n\\t\\tif err != nil {\\n\\t\\t\\treturn nil, err\\n\\t\\t}\\n\\t\\tout := &types.RetrievalResult{Results: results}\\n\\t\\tif params.Rerank != nil {\\n\\t\\t\\tout.Meta.Rerank = &types.RerankDiagnostics{\\n\\t\\t\\t\\tOutcome:        types.RerankOutcomeDisabled,\\n\\t\\t\\t\\tCandidateCount: len(results),\\n"]]}, "internal/application/service/retrieval_only.go": {"line_count": 0, "regions": [[1, ""]]}, "internal/application/service/retrieval_only_test.go": {"line_count": 0, "regions": [[1, ""]]}, "internal/application/service/session_knowledge_qa.go": {"line_count": 1400, "regions": [[816, "func (s *sessionService) SearchKnowledge(ctx context.Context,\\n\\tknowledgeBaseIDs []string, knowledgeIDs []string, tagScopes []types.TagScope, query string,\\n\\topts *types.KnowledgeSearchOptions,\\n) (*types.RetrievalResult, error) {\\n\\tlogger.Info(ctx, \\"Start knowledge base search without LLM summary\\")\\n\\tlogger.Infof(ctx, \\"Knowledge base search parameters, knowledge base IDs: %v, knowledge IDs: %v, tag scopes: %d, query: %s\\",\\n\\t\\tknowledgeBaseIDs, knowledgeIDs, len(tagScopes), query)\\n\\tif opts == nil {\\n\\t\\topts = &types.KnowledgeSearchOptions{}\\n\\t}\\n\\tif opts.DisableVectorMatch && opts.DisableKeywordsMatch {\\n\\t\\treturn nil, apperrors.NewBadRequestError(\\"disable_vector_match and disable_keywords_match cannot both be true\\")\\n\\t}\\n\\n\\t// Get tenant ID from context\\n\\ttenantID, ok := types.TenantIDFromContext(ctx)\\n\\tif !ok {\\n\\t\\tlogger.Error(ctx, \\"Failed to get tenant ID from context\\")\\n\\t\\treturn nil, fmt.Errorf(\\"workspace ID not found in context\\")\\n\\t}\\n"], [975, "\\t\\treturn []*types.SearchResult{}, nil\\n\\t}\\n\\n\\t// Use specific event list, only including retrieval-related events, not LLM summarization\\n\\tsearchEvents := []types.EventType{\\n\\t\\ttypes.CHUNK_SEARCH, // Vector search\\n\\t\\ttypes.CHUNK_RERANK, // Rerank search results\\n\\t\\ttypes.CHUNK_MERGE,  // Merge search results\\n\\t\\ttypes.FILTER_TOP_K, // Filter top K results\\n\\t}\\n\\n\\tlogger.Infof(ctx, \\"Trigger search event list: %v\\", searchEvents)\\n\\n\\tfor _, event := range searchEvents {\\n\\t\\tlogger.Infof(ctx, \\"Starting to trigger search event: %v\\", event)\\n\\t\\tstageCtx, stageSpan := langfuse.GetManager().StartSpan(ctx, langfuse.SpanOptions{\\n\\t\\t\\tName: \\"pipeline.\\" + string(event),\\n\\t\\t\\tMetadata: map[string]interface{}{\\n\\t\\t\\t\\t\\"event_type\\": string(event),\\n\\t\\t\\t\\t\\"flow\\":       \\"search_knowledge\\",\\n"]]}, "internal/router/retrieval_only.go": {"line_count": 0, "regions": [[1, ""]]}, "internal/router/retrieval_only_test.go": {"line_count": 0, "regions": [[1, ""]]}, "internal/router/router.go": {"line_count": 376, "regions": [[137, "\\t\\tAllowCredentials: true,\\n\\t\\tMaxAge:           12 * time.Hour,\\n\\t}))\\n\\n\\t// 基础中间件（不需要认证）\\n\\tr.Use(middleware.RequestID())\\n\\tr.Use(middleware.Language())\\n\\tr.Use(middleware.Logger())\\n\\tr.Use(middleware.Recovery())\\n\\tr.Use(middleware.ErrorHandler())\\n\\n\\t// 健康检查（不需要认证）\\n\\tr.GET(\\"/health\\", func(c *gin.Context) {\\n\\t\\tc.JSON(200, gin.H{\\"status\\": \\"ok\\"})\\n\\t})\\n\\n\\t// Swagger API 文档（仅在非生产环境下启用）\\n\\t// 通过 GIN_MODE 环境变量判断：release 模式下禁用 Swagger\\n\\tif gin.Mode() != gin.ReleaseMode {\\n\\t\\tr.GET(\\"/swagger/*any\\", ginSwagger.WrapHandler(swaggerFiles.Handler,\\n"], [179, "\\tRegisterIMRoutes(r, params.IMHandler)\\n"]]}}'
)


def load():
    manifest = json.loads((PATCH_ROOT / "retrieval-only-manifest.json").read_text())
    patch = (PATCH_ROOT / manifest["patch"]["path"]).read_bytes()
    return manifest, patch


def materialize(root):
    for relative, fixture in FROZEN_PREDECESSOR.items():
        if fixture["line_count"] == 0:
            continue
        lines = ["\n"] * fixture["line_count"]
        for start, text in fixture["regions"]:
            excerpt = text.splitlines(keepends=True)
            lines[start - 1 : start - 1 + len(excerpt)] = excerpt
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(lines))


def apply(root, patch, *, dry_run=False):
    executable = shutil.which("patch")
    if executable is None:
        pytest.fail("Existing system patch is required; no dependency installation in this test")
    command = [executable, "-p1", "--batch", "--fuzz=0"]
    if dry_run:
        command.append("--dry-run")
    try:
        return subprocess.run(
            command, input=patch, cwd=root, capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        log.error("retrieval_profile_patch_process_failed error_type=%s", type(error).__name__)
        pytest.fail("Could not validate the retrieval-only patch process")


def test_profile_manifest_binds_release_predecessor_and_all_source_images():
    manifest, patch = load()
    assert manifest["upstream"]["release_sha"] == "f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7"
    assert hashlib.sha256(patch).hexdigest() == manifest["patch"]["sha256"]
    assert (
        hashlib.sha256((PATCH_ROOT / manifest["predecessor"]["path"]).read_bytes()).hexdigest()
        == manifest["predecessor"]["sha256"]
    )
    assert manifest["profile"]["environment"] == "WEKNORA_RETRIEVAL_ONLY"
    assert manifest["profile"]["enabled_value"] == "1"
    assert manifest["profile"]["default"] == "disabled"
    assert set(FROZEN_PREDECESSOR) == {row["path"] for row in manifest["files"]}
    for row in manifest["files"]:
        assert re.fullmatch("[a-f0-9]{64}", row["preimage_sha256"])
        assert re.fullmatch("[a-f0-9]{64}", row["postimage_sha256"])
        assert row["preimage_sha256"] != row["postimage_sha256"]
        if row["introduced_by_patch"]:
            assert row["upstream_url"] is None
    binding = {
        "upstream_sha": manifest["upstream"]["release_sha"],
        "predecessor_sha256": manifest["predecessor"]["sha256"],
        "patch_sha256": manifest["patch"]["sha256"],
        "postimages": {row["path"]: row["postimage_sha256"] for row in manifest["files"]},
    }
    assert (
        hashlib.sha256(
            json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == manifest["combined_source_binding_sha256"]
    )
    assert manifest["verification"]["go_runtime_tests"] == "NOT_RUN"
    assert manifest["verification"]["actual_service"] == "NOT_RUN"
    assert manifest["license"]["spdx"] == "MIT"


def test_profile_patch_applies_exact_predecessor_and_guards_before_queue(tmp_path):
    _, patch = load()
    materialize(tmp_path)
    result = apply(tmp_path, patch)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    service = tmp_path / "internal/application/service"
    config = (service / "knowledge_process_config.go").read_text()
    assert "defer func() { eff = enforceRetrievalOnlyConfig(eff) }()" in config
    assert config.count("if !retrievalOnlyEnabled() && enableMultimodel") == 2
    table = (service / "extract.go").read_text()
    assert table.index("if retrievalOnlyEnabled() {") < table.index("summary explicitly disabled")
    post = (service / "knowledge_post_process.go").read_text()
    assert "willSpawnWiki := !retrievalOnlyEnabled()" in post
    assert "willSpawnAutoTag := !retrievalOnlyEnabled()" in post
    profile = (service / "knowledgebase_profile.go").read_text()
    assert "if retrievalOnlyEnabled() || enqueuer == nil" in profile
    process = (service / "knowledge_process.go").read_text()
    assert "options.EnableMultimodel = false" in process
    assert 'parserEngine = "builtin"' in process
    assert "mergedOverrides = map[string]string{}" in process
    assert "if retrievalOnlyEnabled() || s.task == nil" in process
    router = (tmp_path / "internal/router/router.go").read_text()
    assert router.index("r.Use(retrievalOnlyMiddleware())") < router.index("RegisterIMRoutes(")
    go_test = (service / "retrieval_only_test.go").read_text()
    assert "TestRetrievalOnlyPostprocessCompletesWithoutEnrichment" in go_test
    assert "types.ParseStatusCompleted" in go_test
    assert "require.Empty(t, queue.taskTypes)" in go_test
    raw_search = (service / "knowledgebase_search_rerank.go").read_text()
    assert "if retrievalOnlyEnabled() && params.Rerank.IsEnabled()" in raw_search
    general_search = (service / "session_knowledge_qa.go").read_text()
    assert "copy.Rerank = &types.RerankOptions{Enabled: &disabled}" in general_search
    assert (
        "searchEvents = []types.EventType{types.CHUNK_SEARCH, types.CHUNK_MERGE, types.FILTER_TOP_K}"
        in general_search
    )
    assert "TestRetrievalOnlyRawRerankRejectedBeforeProvider" in go_test
    assert "TestRetrievalOnlySearchNeverResolvesOrRunsRerank" in go_test
    assert (
        "TestRetrievalOnlyRouteAdmission"
        in (tmp_path / "internal/router/retrieval_only_test.go").read_text()
    )


def test_profile_patch_refuses_drifted_predecessor(tmp_path):
    _, patch = load()
    materialize(tmp_path)
    path = tmp_path / "internal/application/service/knowledge_process_config.go"
    text = path.read_text()
    assert "func ResolveProcessConfig(" in text
    path.write_text(text.replace("func ResolveProcessConfig(", "func SourceDriftConfig(", 1))
    result = apply(tmp_path, patch, dry_run=True)
    assert result.returncode != 0
    assert "failed" in (result.stdout + result.stderr).decode("utf-8", "replace").casefold()
