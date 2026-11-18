/* 登录卡：令牌输入，成功后触发 done */
window.LoginPage = {
  name: "LoginPage",
  emits: ["done"],
  data() {
    return { token: "", busy: false, err: "" };
  },
  methods: {
    async submit() {
      if (this.busy) return;
      this.busy = true;
      this.err = "";
      var ok = await authWith(this.token.trim());
      this.busy = false;
      if (ok) {
        activeToken = this.token.trim();
        try { localStorage.setItem("qvq_token", activeToken); } catch (e) {}
        stripUrlToken();
        this.$emit("done");
      } else {
        this.err = t("login_failed");
      }
    },
  },
  template: [
    '<form class="qvq-login-card" @submit.prevent="submit">',
    '  <div class="qvq-login-title">QvQ<span>Chat</span></div>',
    '  <div class="qvq-login-sub">{{ t("login_hint") }}</div>',
    '  <n-input v-model:value="token" type="password" show-password-on="click" size="large"',
    '           :placeholder="t(\'login_placeholder\')"/>',
    '  <n-button type="primary" block size="large" attr-type="submit"',
    '            style="margin-top:16px" :loading="busy">{{ t("login_btn") }}</n-button>',
    '  <div class="cf-error" v-if="err">{{ err }}</div>',
    '</form>',
  ].join(""),
};
