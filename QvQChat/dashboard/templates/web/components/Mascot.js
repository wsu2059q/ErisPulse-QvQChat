/* 吉祥物：小机器人，mood 控制待机动作，空闲时随机做一个动作 */
window.Mascot = {
  name: "Mascot",
  props: {
    size: { type: Number, default: 30 },
    mood: { type: String, default: "idle" },
  },
  data() {
    return { auto: "" };
  },
  computed: {
    current() { return this.auto || this.mood; },
  },
  mounted() {
    this.schedule();
  },
  beforeUnmount() {
    clearTimeout(this._idleTimer);
    clearTimeout(this._autoTimer);
  },
  methods: {
    schedule() {
      var self = this;
      clearTimeout(self._idleTimer);
      self._idleTimer = setTimeout(function () {
        var pool = ["coffee", "wave", "nod", "think"];
        self.auto = pool[Math.floor(Math.random() * pool.length)];
        clearTimeout(self._autoTimer);
        self._autoTimer = setTimeout(function () {
          self.auto = "";
          self.schedule();
        }, 2800);
      }, 14000 + Math.random() * 12000);
    },
  },
  template: [
    '<div class="qvq-mascot" :class="current"',
    '     :style="{ width: size + \'px\', height: size + \'px\' }">',
    '  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"',
    '       stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">',
    '    <g class="m-antenna">',
    '      <path d="M12 7V4" stroke-dasharray="2 2"/>',
    '      <circle class="m-tip" cx="12" cy="3" r="1" fill="currentColor" stroke="none"/>',
    '    </g>',
    '    <rect x="4" y="7" width="16" height="12" rx="2" stroke-dasharray="3 2"/>',
    '    <g class="m-eyes">',
    '      <circle cx="9" cy="13" r="1.2" fill="currentColor" stroke="none"/>',
    '      <circle cx="15" cy="13" r="1.2" fill="currentColor" stroke="none"/>',
    '    </g>',
    '    <path d="M4 17l-2 2M20 17l2 2" stroke-dasharray="2 2"/>',
    '    <g class="m-arm">',
    '      <path d="M20.6 13.4 22.4 11"/>',
    '      <circle cx="22.8" cy="10.5" r="0.9" fill="currentColor" stroke="none"/>',
    '    </g>',
    '    <g class="m-cup">',
    '      <path class="m-cup-body" d="M9.4 19.4h4v3a1.1 1.1 0 0 1-1.1 1.1H10.5a1.1 1.1 0 0 1-1.1-1.1z"/>',
    '      <path d="M13.4 20.2h1a0.9 0.9 0 0 1 0 1.9h-1"/>',
    '      <path d="M10.4 18.4c0-.5.5-.5.5-1M12.4 18.4c0-.5.5-.5.5-1"/>',
    '    </g>',
    '    <text class="m-zz" x="19" y="7" font-size="3.2" fill="currentColor" stroke="none">z</text>',
    '  </svg>',
    '</div>',
  ].join(""),
};
