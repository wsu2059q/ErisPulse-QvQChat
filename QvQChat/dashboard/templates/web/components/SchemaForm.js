/* 配置控件：按 widget 渲染单项，值经 update:modelValue 回传 */
window.SchemaForm = {
  name: "SchemaForm",
  props: {
    field: { type: Object, required: true },
    modelValue: null,
    error: { type: String, default: "" },
    dirty: { type: Boolean, default: false },
    hideHead: { type: Boolean, default: false },
  },
  emits: ["update:modelValue", "revert"],
  computed: {
    widget() { return this.field.widget || "text"; },
    wide() {
      var w = this.widget;
      return w === "json" || w === "lines" || w === "list" || w === "checks" || w === "model_map";
    },
    parts() {
      return {
        title: QvQ.fieldTitle(this.field.description, this.field.key),
        desc: QvQ.fieldDesc(this.field.description, this.field.key),
      };
    },
    choices() {
      return (this.field.choices || []).map(function (v) {
        return { label: String(v), value: v };
      });
    },
    hint() {
      var text = this.parts.desc || "";
      if (this.field.choices && this.field.choices.length) {
        var extra = this.field.choices.length + " " + t("cf_options_n");
        text = text ? text + " · " + extra : extra;
      }
      return text;
    },
    hasChoices() {
      return this.widget === "text" && (this.field.choices || []).length > 0;
    },
    multiChoices() {
      var w = this.widget;
      return (w === "list" || w === "lines") && (this.field.choices || []).length > 0;
    },
    mapValue() {
      return this.modelValue && typeof this.modelValue === "object" ? this.modelValue : {};
    },
    options() {
      var raw = this.field.options || [];
      return raw.map(function (o) {
        return typeof o === "string" ? { label: o, value: o } : o;
      });
    },
    checked() { return this.modelValue || []; },
    num() {
      var v = this.modelValue;
      if (v === null || v === undefined || v === "") return null;
      return Number(v);
    },
    min() { return this.field.min === null || this.field.min === undefined ? undefined : Number(this.field.min); },
    max() { return this.field.max === null || this.field.max === undefined ? undefined : Number(this.field.max); },
    step() { return this.field.step === null || this.field.step === undefined ? undefined : Number(this.field.step); },
    text() {
      return this.modelValue === null || this.modelValue === undefined ? "" : String(this.modelValue);
    },
  },
  methods: {
    set(v) { this.$emit("update:modelValue", v); },
    setKind(kind, value) {
      var next = Object.assign({}, this.mapValue);
      if (value) next[kind] = value;
      else delete next[kind];
      this.set(next);
    },
  },
  template: [
    '<div class="cf-field" :class="{ wide: wide, bare: hideHead, danger: field.dangerous, err: !!error }">',
    '  <div class="cf-side" v-if="!hideHead">',
    '    <div class="cf-label" :title="field.key">',
    '      <button v-if="dirty" type="button" class="cf-dot" :title="t(\'cf_revert\')"',
    '              @click="$emit(\'revert\')"></button>',
    '      <span class="cf-title">{{ parts.title }}</span>',
    '      <span v-if="field.dangerous" class="cf-badge">{{ t("settings_dangerous") }}</span>',
    '    </div>',
    '    <div class="cf-desc" v-if="hint" :title="hint">{{ hint }}</div>',
    '  </div>',
    '  <div class="cf-control">',
    '    <n-switch v-if="widget === \'switch\'" :value="!!modelValue" @update:value="set"/>',
    '    <n-input-number v-else-if="widget === \'number\'" :value="num" :min="min" :max="max" :step="step"',
    '                    :placeholder="field.placeholder || \'\'" style="width:180px" @update:value="set"/>',
    '    <div v-else-if="widget === \'slider\'" class="cf-slider">',
    '      <n-slider :value="num" :min="min === undefined ? 0 : min" :max="max" :step="step || 0.05"',
    '                @update:value="set"/>',
    '      <span class="cf-slider-val">{{ num }}</span>',
    '    </div>',
    '    <n-select v-else-if="widget === \'select\'" :value="modelValue" :options="options"',
    '              @update:value="set"/>',
    '    <n-checkbox-group v-else-if="widget === \'checks\'" :value="checked" @update:value="set"',
    '                      class="cf-checks">',
    '      <n-checkbox v-for="o in options" :key="o.value" :value="o.value"',
    '                  class="cf-chip" :class="{ on: checked.indexOf(o.value) >= 0 }">',
    '        {{ o.label }}',
    '      </n-checkbox>',
    '    </n-checkbox-group>',
    '    <n-input v-else-if="widget === \'json\'" type="textarea" :rows="5" class="cf-mono"',
    '             :value="text" @update:value="set"/>',
    '    <n-select v-else-if="multiChoices" multiple filterable clearable :value="checked"',
    '              :options="choices" :placeholder="field.placeholder || t(\'cf_inherit\')"',
    '              @update:value="set"/>',
    '    <n-input v-else-if="widget === \'lines\' || widget === \'list\'" type="textarea" :rows="3"',
    '             :value="text" :placeholder="field.placeholder || \'\'" @update:value="set"/>',
    '    <div v-else-if="widget === \'model_map\'" class="cf-maplist">',
    '      <div v-for="kind in (field.items || [])" :key="kind" class="cf-maprow">',
    '        <span class="cf-mapcat">{{ t("task_kind_" + kind) }}</span>',
    '        <n-select :value="mapValue[kind] || null" :options="choices" filterable clearable',
    '                  size="small" :placeholder="t(\'cf_inherit\')"',
    '                  @update:value="setKind(kind, $event)"/>',
    '      </div>',
    '    </div>',
    '    <n-select v-else-if="hasChoices" :value="modelValue || null" :options="choices"',
    '              filterable clearable :placeholder="field.placeholder || t(\'cf_inherit\')"',
    '              @update:value="set($event || \'\')"/>',
    '    <n-input v-else :value="text" :type="field.secret ? \'password\' : \'text\'"',
    '             :show-password-on="field.secret ? \'click\' : undefined"',
    '             :placeholder="field.placeholder || \'\'" @update:value="set"/>',
    '    <div class="cf-error" v-if="error">{{ error }}</div>',
    '  </div>',
    '</div>',
  ].join(""),
};
