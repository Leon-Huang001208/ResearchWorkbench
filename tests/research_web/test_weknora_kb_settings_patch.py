"""Verify the pinned profile-aware KB settings patch without a frontend build.

Sparse predecessor excerpts bind exact patch context. Full source hashes are
build admission inputs and must be verified against the real fixed checkout.
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
    '{"frontend/src/api/initialization/index.ts": {"line_count": 740, "regions": [[9, "    apiKey?: boolean;\\n}\\n\\nexport interface COSCredentialStatus {\\n    secretId?: boolean;\\n    secretKey?: boolean;\\n}\\n\\n// 初始化配置数据类型\\nexport interface InitializationConfig {\\n    llm: {\\n        source: string;\\n        modelName: string;\\n        baseUrl?: string;\\n        /** @deprecated Use credentials.apiKey from GET responses */\\n        apiKey?: string;\\n        credentials?: ModelCredentialStatus;\\n    };\\n    embedding: {\\n        source: string;\\n"]]}, "frontend/src/utils/retrievalOnlyKBSettings.d.mts": {"line_count": 0, "regions": [[1, ""]]}, "frontend/src/utils/retrievalOnlyKBSettings.mjs": {"line_count": 0, "regions": [[1, ""]]}, "frontend/src/views/knowledge/KnowledgeBaseEditorModal.test.mjs": {"line_count": 52, "regions": [[43, "test(\'edit mode forwards image_processing_config in the update payload\', () => {\\n  // Regression: the edit branch built data.image_processing_config but never\\n  // put it into updateConfig, so KB-editor changes to the image classification\\n  // settings were silently dropped (create worked, later edits did not).\\n  const editBranch = source.match(\\n    /(\\\\/\\\\/ 编辑模式：分别更新基本信息[\\\\s\\\\S]*?await updateKnowledgeBase\\\\(kbId, \\\\{)/\\n  )?.[1]\\n  assert.ok(editBranch, \'expected to find the edit-mode update block\')\\n  assert.match(editBranch, /if \\\\(data\\\\.image_processing_config\\\\) \\\\{\\\\s*updateConfig\\\\.image_processing_config = data\\\\.image_processing_config\\\\s*\\\\}/)\\n})\\n"]]}, "frontend/src/views/knowledge/KnowledgeBaseEditorModal.vue": {"line_count": 2565, "regions": [[151, "              <label class=\\"form-label\\">{{ $t(\'knowledgeEditor.basic.descriptionLabel\') }}</label>\\n              <t-textarea\\n                v-model=\\"formData.description\\"\\n                :placeholder=\\"$t(\'knowledgeEditor.basic.descriptionPlaceholder\')\\"\\n                :maxlength=\\"200\\"\\n                :autosize=\\"{ minRows: 3, maxRows: 6 }\\"\\n              />\\n            </div>\\n\\n            <!-- AI 生成的知识库描述（仅编辑模式、文档型知识库） -->\\n            <div v-if=\\"editorMode === \'edit\' && !isFAQ\\" class=\\"form-item\\">\\n              <label class=\\"form-label\\">{{ $t(\'knowledgeEditor.basic.profile.title\') }}</label>\\n              <div class=\\"kb-profile-card\\" :class=\\"{ \'is-empty\': !generatedProfileHasText }\\">\\n                <template v-if=\\"generatedProfileHasText\\">\\n                  <p v-if=\\"generatedProfile?.gist\\" class=\\"kb-profile-gist\\">{{ generatedProfile.gist }}</p>\\n                  <div v-if=\\"generatedProfile?.topics?.length\\" class=\\"kb-profile-topics\\">\\n                    <t-tag\\n                      v-for=\\"topic in generatedProfile.topics\\"\\n                      :key=\\"topic\\"\\n                      size=\\"small\\"\\n                      theme=\\"primary\\"\\n"], [240, "        </div>\\n      </div>\\n\\n      <!-- 模型配置 -->\\n      <div v-show=\\"currentSection === \'models\'\\" class=\\"section\\">\\n        <KBModelConfig\\n          ref=\\"modelConfigRef\\"\\n          v-if=\\"formData\\"\\n          :config=\\"formData.modelConfig\\"\\n          :has-files=\\"hasFiles\\"\\n          :wiki-enabled=\\"formData.indexingStrategy?.wikiEnabled\\"\\n          :rag-enabled=\\"formData.indexingStrategy?.vectorEnabled || formData.indexingStrategy?.keywordEnabled\\"\\n          :all-models=\\"allModels\\"\\n          @update:config=\\"handleModelConfigUpdate\\"\\n        />\\n      </div>\\n\\n      <!-- VectorStore 绑定 -->\\n      <div v-show=\\"currentSection === \'vectorStore\'\\" class=\\"section\\">\\n        <KBVectorStoreSettings\\n"], [638, "const displaySchema = computed<ImageAttrSchema>(\\n  () => imageAttrSchema.value ?? FALLBACK_IMAGE_ATTR_SCHEMA,\\n)\\nasync function loadImageAttrSchema(kbId: string) {\\n  try {\\n    imageAttrSchema.value = await fetchImageAttrSchema(kbId)\\n  } catch {\\n    imageAttrSchema.value = null\\n  }\\n}\\nimport { updateKBConfig, type KBModelConfigRequest } from \'@/api/initialization\'\\nimport { useChatResourcesStore } from \'@/stores/chatResources\'\\nimport { selectInitialModelId } from \'@/utils/modelDefaults\'\\nimport { copyWithToast } from \'@/utils/clipboard\'\\nimport { useEditorResourcesStore } from \'@/stores/editorResources\'\\nimport { useUIStore } from \'@/stores/ui\'\\nimport { useAuthStore } from \'@/stores/auth\'\\nimport KBModelConfig from \'./settings/KBModelConfig.vue\'\\nimport KBParserSettings from \'./settings/KBParserSettings.vue\'\\nimport KBStorageSettings from \'./settings/KBStorageSettings.vue\'\\nimport KBChunkingSettings from \'./settings/KBChunkingSettings.vue\'\\n"], [730, "  window.addEventListener(KB_EDITOR_FOCUS_SECTION_EVENT, onKbEditorFocusSection)\\n})\\n\\nonBeforeUnmount(() => {\\n  window.removeEventListener(KB_EDITOR_FOCUS_SECTION_EVENT, onKbEditorFocusSection)\\n})\\nconst saving = ref(false)\\nconst loading = ref(false)\\nconst allModels = ref<any[]>([])\\nconst hasFiles = ref(false)\\n// AI-generated knowledge-base description (edit mode only). Kept outside\\n// formData because it is never submitted: the backend owns it.\\nconst generatedProfile = ref<KnowledgeBaseProfile | null>(null)\\nconst generatingProfile = ref(false)\\nconst generatedProfileHasText = computed(() => {\\n  const p = generatedProfile.value\\n  return !!(p && (p.gist || p.topics?.length || p.typical_questions?.length))\\n})\\nconst generatedProfileMeta = computed(() => {\\n  const p = generatedProfile.value\\n"], [845, "  if (canViewActivity.value) {\\n    items.push({ key: \'activity\', icon: \'history\', label: t(\'knowledgeEditor.sidebar.activity\') })\\n  }\\n  return items\\n})\\n\\n// 左侧导航分组（与 AgentEditorModal 对齐）\\nconst navGroups = computed(() => {\\n  const itemMap = new Map(navItems.value.map((item) => [item.key, item]))\\n  const pickItems = (keys: string[]) =>\\n    keys.map((key) => itemMap.get(key)).filter(Boolean) as typeof navItems.value\\n  return [\\n    {\\n      key: \'basic\',\\n      label: t(\'knowledgeEditor.navGroups.basic\'),\\n      items: pickItems([\'basic\', \'models\', \'vectorStore\', \'faq\']),\\n    },\\n    {\\n      key: \'processing\',\\n      label: t(\'knowledgeEditor.navGroups.processing\'),\\n      items: pickItems([\'parser\', \'chunking\', \'multimodal\', \'asr\', \'graph\', \'advanced\']),\\n"], [1079, "// 加载知识库数据（编辑模式）\\nconst loadKBData = async (\\n  kbIdOverride?: string,\\n  generation = kbEditorLoadGeneration,\\n) => {\\n  const kbId = kbIdOverride ?? activeKbId.value\\n  if (editorMode.value !== \'edit\' || !kbId) return\\n  \\n  loading.value = true\\n  try {\\n    const [kbInfo, filesResult] = await Promise.all([\\n      getKnowledgeBaseById(kbId),\\n      listKnowledgeFiles(kbId, { page: 1, page_size: 1 })\\n    ])\\n\\n    if (!isCurrentKBLoad(generation, kbId)) return\\n    \\n    if (!kbInfo || !kbInfo.data) {\\n      throw new Error(t(\'knowledgeEditor.messages.notFound\'))\\n    }\\n\\n    const kb = kbInfo.data\\n    hasFiles.value = (filesResult as any)?.total > 0\\n    generatedProfile.value = (kb as any).generated_profile || null\\n    kbCreatorId.value = (kb as any).creator_id || \'\'\\n    kbTenantId.value = Number((kb as any).tenant_id || 0)\\n\\n    // 设置表单数据\\n    const kbType = (kb.type as \'document\' | \'faq\') || \'document\'\\n    formData.value = {\\n      type: kbType,\\n"], [1293, "const toggleVectorIndexing = () => {\\n  if (!formData.value) return\\n  if (isIndexingLocked.value) return\\n  const next = !formData.value.indexingStrategy.vectorEnabled\\n  formData.value.indexingStrategy.vectorEnabled = next\\n  formData.value.indexingStrategy.keywordEnabled = next\\n}\\n\\nconst toggleWikiIndexing = () => {\\n  if (!formData.value) return\\n  if (isIndexingLocked.value) return\\n  formData.value.indexingStrategy.wikiEnabled = !formData.value.indexingStrategy.wikiEnabled\\n}\\n\\nconst handleChunkingConfigUpdate = (config: any) => {\\n  if (formData.value) {\\n    formData.value.chunkingConfig = { ...config }\\n    // 用户已经手动触达分块设置，后续索引策略切换不再覆盖这些值\\n    chunkingDirty.value = true\\n  }\\n}\\n"], [1493, "  }\\n\\n  // 验证模型配置 - embedding 模型仅在检索索引启用时必须\\n  const needsEmbedding = formData.value.indexingStrategy?.vectorEnabled || formData.value.indexingStrategy?.keywordEnabled\\n  if (needsEmbedding && !formData.value.modelConfig.embeddingModelId) {\\n    MessagePlugin.warning(t(\'knowledgeEditor.indexing.embeddingRequired\'))\\n    currentSection.value = \'models\'\\n    return false\\n  }\\n\\n  if (!formData.value.modelConfig.llmModelId) {\\n    MessagePlugin.warning(t(\'knowledgeEditor.messages.summaryRequired\'))\\n    currentSection.value = \'models\'\\n    return false\\n  }\\n\\n  // 验证多模态配置（如果启用）\\n  if (formData.value.multimodalConfig.enabled && !formData.value.multimodalConfig.vllmModelId) {\\n    MessagePlugin.warning(t(\'knowledgeEditor.messages.multimodalInvalid\'))\\n    currentSection.value = \'multimodal\'\\n    return false\\n"], [1688, "    data.extract_config = {\\n      enabled: !!formData.value.nodeExtractConfig.enabled,\\n      text: formData.value.nodeExtractConfig.text || \'\',\\n      tags: formData.value.nodeExtractConfig.tags || [],\\n      nodes: formData.value.nodeExtractConfig.nodes || [],\\n      relations: formData.value.nodeExtractConfig.relations || [],\\n      custom_instructions: formData.value.nodeExtractConfig.customInstructions || \'\'\\n    }\\n  }\\n\\n  return data\\n}\\n\\n// 提交表单\\nconst handleSubmit = async () => {\\n  if (!validateForm()) {\\n    return\\n  }\\n\\n  // 编辑模式下，若已有文件且存储引擎发生了变化，弹窗确认\\n  if (\\n"], [1903, "    saving.value = false\\n  }\\n}\\n\\n// 重置所有状态\\nconst resetState = () => {\\n  savedKbId.value = null\\n  currentSection.value = \'basic\'\\n  formData.value = null\\n  hasFiles.value = false\\n  initialStorageProvider.value = \'\'\\n  tenantDefaultStorageProvider.value = \'local\'\\n  initialIndexingStrategy.value = null\\n  saving.value = false\\n  loading.value = false\\n  chunkingDirty.value = false\\n  kbCreatorId.value = \'\'\\n  kbTenantId.value = 0\\n}\\n\\n"]]}, "frontend/src/views/knowledge/settings/KBModelConfig.vue": {"line_count": 248, "regions": [[1, "<template>\\n  <div class=\\"kb-model-config\\">\\n    <div class=\\"section-header\\">\\n      <h2>{{ $t(\'knowledgeEditor.models.title\') }}</h2>\\n      <p class=\\"section-description\\">{{ $t(\'knowledgeEditor.models.description\') }}</p>\\n    </div>\\n\\n    <div class=\\"settings-group\\">\\n      <!-- LLM 大语言模型 -->\\n      <div class=\\"setting-row\\" data-guide=\\"kb-create-llm\\">\\n        <div class=\\"setting-info\\">\\n          <label>{{ $t(\'knowledgeEditor.models.llmLabel\') }} <span class=\\"required\\">*</span></label>\\n          <p class=\\"desc\\">{{ $t(\'knowledgeEditor.models.llmDesc\') }}</p>\\n        </div>\\n        <div class=\\"setting-control\\">\\n          <ModelSelector\\n            ref=\\"llmSelectorRef\\"\\n            model-type=\\"KnowledgeQA\\"\\n            :selected-model-id=\\"config.llmModelId\\"\\n            :all-models=\\"allModels\\"\\n"], [90, "interface ModelConfig {\\n  llmModelId?: string\\n  embeddingModelId?: string\\n  vllmModelId?: string\\n  wikiSynthesisModelId?: string\\n}\\n\\ninterface Props {\\n  config: ModelConfig\\n  hasFiles: boolean\\n  wikiEnabled?: boolean\\n  ragEnabled?: boolean\\n  allModels?: any[]\\n}\\n\\nconst props = defineProps<Props>()\\n\\nconst emit = defineEmits<{\\n  \'update:config\': [value: ModelConfig]\\n}>()\\n"]]}, "internal/handler/initialization.go": {"line_count": 2793, "regions": [[90, "\\t\\tknowledgeService: knowledgeService,\\n\\t\\tollamaService:    ollamaService,\\n\\t\\tdocumentReader:   documentReader,\\n\\t\\tpooler:           pooler,\\n\\t\\tstorageResolver:  storageResolver,\\n\\t}\\n}\\n\\n// KBModelConfigRequest 知识库模型配置请求（简化版，只传模型ID）\\ntype KBModelConfigRequest struct {\\n\\tLLMModelID       string           `json:\\"llmModelId\\"       binding:\\"required\\"`\\n\\tEmbeddingModelID string           `json:\\"embeddingModelId\\"` // optional when RAG indexing is disabled\\n\\tVLMConfig        *types.VLMConfig `json:\\"vlm_config\\"`\\n\\tASRConfig        *types.ASRConfig `json:\\"asr_config\\"`\\n\\n\\t// 文档分块配置\\n\\tDocumentSplitting struct {\\n\\t\\tChunkSize         int                      `json:\\"chunkSize\\"`\\n\\t\\tChunkOverlap      int                      `json:\\"chunkOverlap\\"`\\n\\t\\tSeparators        []string                 `json:\\"separators\\"`\\n\\t\\tParserEngineRules []types.ParserEngineRule `json:\\"parserEngineRules,omitempty\\"`\\n"], [241, "\\tctx := c.Request.Context()\\n\\tkbIdStr := utils.SanitizeForLog(c.Param(\\"kbId\\"))\\n\\n\\tvar req KBModelConfigRequest\\n\\tif err := c.ShouldBindJSON(&req); err != nil {\\n\\t\\tlogger.Error(ctx, \\"Failed to parse KB config request\\", err)\\n\\t\\tc.Error(errors.NewBadRequestError(err.Error()))\\n\\t\\treturn\\n\\t}\\n\\n\\t// 获取知识库信息\\n\\tkb, err := h.kbService.GetKnowledgeBaseByID(ctx, kbIdStr)\\n\\tif err != nil || kb == nil {\\n\\t\\tlogger.ErrorWithFields(ctx, err, map[string]interface{}{\\"kbId\\": utils.SanitizeForLog(kbIdStr)})\\n\\t\\tc.Error(errors.NewNotFoundError(\\"知识库不存在\\"))\\n\\t\\treturn\\n\\t}\\n\\townWorkspace, err := kbSettingsAccess(c, kb)\\n\\tif err != nil {\\n\\t\\t_ = c.Error(err)\\n"], [270, "\\t\\t\\t\\tPageSize: 1,\\n\\t\\t\\t}, types.KnowledgeListFilter{})\\n\\t\\tif err == nil && knowledgeList != nil && knowledgeList.Total > 0 {\\n\\t\\t\\tlogger.Error(ctx, \\"Cannot change embedding model when files exist\\")\\n\\t\\t\\tc.Error(errors.NewBadRequestError(\\"知识库中已有文件，无法修改Embedding模型\\"))\\n\\t\\t\\treturn\\n\\t\\t}\\n\\t}\\n\\n\\t// 从数据库获取模型详情并验证\\n\\tllmModel, err := h.modelService.GetModelByID(ctx, req.LLMModelID)\\n\\tif err != nil || llmModel == nil {\\n\\t\\tlogger.Error(ctx, \\"LLM model not found\\")\\n\\t\\tc.Error(errors.NewBadRequestError(\\"LLM模型不存在\\"))\\n\\t\\treturn\\n\\t}\\n\\n\\t// Embedding模型仅在需要时验证（RAG检索启用时）\\n\\tif req.EmbeddingModelID != \\"\\" {\\n\\t\\tembeddingModel, err := h.modelService.GetModelByID(ctx, req.EmbeddingModelID)\\n\\t\\tif err != nil || embeddingModel == nil {\\n\\t\\t\\tlogger.Error(ctx, \\"Embedding model not found\\")\\n\\t\\t\\tc.Error(errors.NewBadRequestError(\\"Embedding模型不存在\\"))\\n\\t\\t\\treturn\\n\\t\\t}\\n\\t}\\n\\n\\t// 更新知识库的模型ID\\n\\tkb.SummaryModelID = req.LLMModelID\\n\\tif req.EmbeddingModelID != \\"\\" {\\n\\t\\tkb.EmbeddingModelID = req.EmbeddingModelID\\n"], [436, "\\t\\t\\tEnabled:            false,\\n\\t\\t\\tCustomInstructions: strings.TrimSpace(req.QuestionGeneration.CustomInstructions),\\n\\t\\t}\\n\\t}\\n\\ttypes.NormalizeKnowledgeBasePromptInstructions(kb)\\n\\tif err := validateKnowledgeBasePromptInstructions(kb); err != nil {\\n\\t\\tc.Error(err)\\n\\t\\treturn\\n\\t}\\n\\n\\t// 保存更新后的知识库\\n\\tif err := h.kbRepository.UpdateKnowledgeBase(ctx, kb); err != nil {\\n\\t\\tlogger.Error(ctx, \\"Failed to update knowledge base\\", err)\\n\\t\\tc.Error(errors.NewInternalServerError(\\"更新知识库失败: \\" + err.Error()))\\n\\t\\treturn\\n\\t}\\n\\n\\tc.JSON(http.StatusOK, gin.H{\\n\\t\\t\\"success\\": true,\\n\\t\\t\\"message\\": \\"配置更新成功\\",\\n"], [1545, "\\t\\t\\"success\\": true,\\n\\t\\t\\"data\\":    config,\\n\\t})\\n}\\n\\n// buildConfigResponse 构建配置响应数据\\nfunc (h *InitializationHandler) buildConfigResponse(ctx context.Context, models []*types.Model,\\n\\tkb *types.KnowledgeBase, hasFiles bool,\\n) map[string]interface{} {\\n\\tconfig := map[string]interface{}{\\n\\t\\t\\"hasFiles\\": hasFiles,\\n\\t}\\n\\t// Integration details describe the owning workspace\'s infrastructure. A\\n\\t// share receiver — even an admin of its own workspace — only learns\\n\\t// whether credentials are configured.\\n\\townWorkspace := kb != nil && kb.TenantID == types.CallerFromContext(ctx).TenantID\\n\\tincludeIntegrationDetail := ownWorkspace && dto.CanViewIntegrationSecrets(ctx)\\n\\n\\t// 按类型分组模型\\n\\tfor _, model := range models {\\n\\t\\tif model == nil {\\n"]]}, "internal/handler/retrieval_only_kb_settings.go": {"line_count": 0, "regions": [[1, ""]]}, "internal/handler/retrieval_only_kb_settings_test.go": {"line_count": 0, "regions": [[1, ""]]}, "internal/router/retrieval_only.go": {"line_count": 50, "regions": [[18, "\\t\\treturn method == http.MethodGet || method == http.MethodHead\\n\\t}\\n\\tif !strings.HasPrefix(path, \\"/api/v1/\\") {\\n\\t\\treturn false\\n\\t}\\n\\tp := strings.TrimPrefix(path, \\"/api/v1/\\")\\n\\tif strings.Contains(p, \\"regenerate\\") || strings.Contains(p, \\"/wiki\\") || strings.Contains(p, \\"/profile/generate\\") || strings.HasSuffix(p, \\"/debug\\") || strings.HasSuffix(p, \\"/test\\") && p != \\"initialization/embedding/test\\" {\\n\\t\\treturn false\\n\\t}\\n\\tif strings.HasPrefix(p, \\"initialization/\\") {\\n\\t\\treturn method == http.MethodGet && strings.HasPrefix(p, \\"initialization/config/\\") || method == http.MethodPost && p == \\"initialization/embedding/test\\"\\n\\t}\\n\\tsegment := strings.SplitN(p, \\"/\\", 2)[0]\\n\\tswitch segment {\\n\\tcase \\"auth\\", \\"users\\", \\"tenants\\", \\"organizations\\", \\"kb-shares\\", \\"shared-knowledge-bases\\", \\"knowledge-bases\\", \\"knowledge\\", \\"chunks\\", \\"models\\", \\"knowledge-search\\", \\"files\\", \\"resources\\", \\"storage-backends\\", \\"storage-providers\\", \\"vector-stores\\":\\n\\t\\treturn true\\n\\tcase \\"system\\", \\"config\\", \\"tasks\\", \\"processing-status\\", \\"version\\":\\n\\t\\treturn method == http.MethodGet || method == http.MethodHead\\n\\tdefault:\\n\\t\\treturn false\\n\\t}\\n"]]}, "internal/router/retrieval_only_kb_settings_test.go": {"line_count": 0, "regions": [[1, ""]]}}'
)


def load():
    manifest = json.loads((PATCH_ROOT / "kb-settings-manifest.json").read_text())
    return manifest, (PATCH_ROOT / manifest["patch"]["path"]).read_bytes()


def materialize(root):
    for relative, fixture in FROZEN_PREDECESSOR.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if fixture["line_count"] == 0:
            continue
        lines = ["\n"] * fixture["line_count"]
        for start, text in fixture["regions"]:
            excerpt = text.splitlines(keepends=True)
            lines[start - 1 : start - 1 + len(excerpt)] = excerpt
        path.write_text("".join(lines))


def apply(root, patch, dry_run=False):
    executable = shutil.which("patch")
    if executable is None:
        pytest.fail("Existing patch executable required; no dependency install here")
    cmd = [executable, "-p1", "--batch", "--fuzz=0"]
    if dry_run:
        cmd.append("--dry-run")
    try:
        return subprocess.run(
            cmd, input=patch, cwd=root, capture_output=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        log.error("kb_settings_patch_process_failed error_type=%s", type(error).__name__)
        pytest.fail("Could not verify KB settings patch process")


def test_kb_settings_manifest_binds_predecessor_and_source_images():
    manifest, patch = load()
    assert manifest["upstream"]["release_sha"] == "f17ee8a8da901bd658a4cb25f40b5fd41adbfdd7"
    predecessor = json.loads((PATCH_ROOT / "retrieval-only-manifest.json").read_text())
    assert manifest["predecessor"]["sha256"] == predecessor["patch"]["sha256"]
    assert (
        manifest["predecessor"]["combined_source_binding_sha256"]
        == predecessor["combined_source_binding_sha256"]
    )
    assert hashlib.sha256(patch).hexdigest() == manifest["patch"]["sha256"]
    assert set(FROZEN_PREDECESSOR) == {row["path"] for row in manifest["files"]}
    for row in manifest["files"]:
        assert re.fullmatch("[a-f0-9]{64}", row["preimage_sha256"])
        assert re.fullmatch("[a-f0-9]{64}", row["postimage_sha256"])
    binding = {
        "predecessor": manifest["predecessor"],
        "patch_sha256": manifest["patch"]["sha256"],
        "postimages": {row["path"]: row["postimage_sha256"] for row in manifest["files"]},
    }
    assert (
        hashlib.sha256(
            json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == manifest["combined_source_binding_sha256"]
    )
    assert manifest["verification"]["actual_service"] == "NOT_RUN"
    assert manifest["verification"]["frontend_build"] == "NOT_RUN"


def test_kb_settings_patch_applies_and_keeps_server_policy_authoritative(tmp_path):
    _, patch = load()
    materialize(tmp_path)
    result = apply(tmp_path, patch)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    handler = (tmp_path / "internal/handler/initialization.go").read_text()
    assert '"retrievalOnly": os.Getenv("WEKNORA_RETRIEVAL_ONLY") == "1"' in handler
    assert "normalizeKBSettingsProfile(ctx, &req)" in handler
    assert 'if req.LLMModelID != "" {' in handler
    assert "enforceKBSettingsProfile(kb)" in handler
    policy = (tmp_path / "internal/handler/retrieval_only_kb_settings.go").read_text()
    assert 'if req.LLMModelID == ""' in policy
    assert 'req.LLMModelID = ""' in policy
    assert "req.QuestionGeneration.Enabled = false" in policy
    assert "kb.IndexingStrategy.WikiEnabled = false" in policy
    vue = (tmp_path / "frontend/src/views/knowledge/KnowledgeBaseEditorModal.vue").read_text()
    marker = vue.index("retrievalOnly.value = serverConfig.retrievalOnly === true")
    assert marker > vue.index("if (!isCurrentKBLoad(generation, kbId)) return")
    assert "requiresKBChatModel(retrievalOnly.value, formData.value.modelConfig.llmModelId)" in vue
    assert "retrievalOnlySubmitFields(data, retrievalOnly.value)" in vue
    assert "const retrievalOnly = ref(false)" in vue
    child = (tmp_path / "frontend/src/views/knowledge/settings/KBModelConfig.vue").read_text()
    assert 'v-if="!retrievalOnly"' in child
    node_test = (
        tmp_path / "frontend/src/views/knowledge/KnowledgeBaseEditorModal.test.mjs"
    ).read_text()
    assert "retrieval-only form policy preserves basic settings" in node_test


def test_kb_settings_patch_rejects_drifted_backend_context(tmp_path):
    _, patch = load()
    materialize(tmp_path)
    path = tmp_path / "internal/handler/initialization.go"
    text = path.read_text()
    old = 'LLMModelID       string           `json:"llmModelId"       binding:"required"`'
    assert old in text
    path.write_text(text.replace(old, "changedSourceField string", 1))
    result = apply(tmp_path, patch, True)
    assert result.returncode != 0
    assert "failed" in (result.stdout + result.stderr).decode("utf-8", "replace").casefold()
