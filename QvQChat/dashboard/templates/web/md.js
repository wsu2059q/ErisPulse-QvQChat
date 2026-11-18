/* escape-first markdown 渲染（自旧前端 mdRender 迁移） */
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

function mdInline(s) {
  return esc(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/\*([^*]+)\*/g, "<i>$1</i>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}

function mdRender(text, streamFix) {
  var src = String(text == null ? "" : text);
  if (streamFix) {
    // 流式中 fence 未闭合（delta 只到一半）时补齐尾部，代码块始终完整渲染
    var fences = (src.match(/```/g) || []).length;
    if (fences % 2 === 1) src += "\n```";
  }
  if (!src.trim()) return "";
  var out = "";
  var segments = src.split(/```/);
  segments.forEach(function (seg, idx) {
    if (idx % 2 === 1) {
      var nl = seg.indexOf("\n");
      var lang = nl >= 0 ? seg.slice(0, nl).trim() : "";
      var body = nl >= 0 ? seg.slice(nl + 1) : seg;
      out += '<div class="qvq-md-block"><div class="qvq-md-head"><span class="qvq-md-lang">' +
        esc(lang || "text") + '</span><button type="button" class="qvq-md-copy">' +
        "copy</button></div><pre class=\"qvq-md-pre\"><code>" + esc(body) + "</code></pre></div>";
      return;
    }
    var html = "";
    var inList = false;
    var lines = seg.split("\n");
    for (var li2 = 0; li2 < lines.length; li2++) {
      var line = lines[li2];
      var h = /^(#{1,6})\s+(.*)$/.exec(line);
      if (h) {
        if (inList) { html += "</ul>"; inList = false; }
        html += "<h" + h[1].length + ">" + mdInline(h[2]) + "</h" + h[1].length + ">";
        continue;
      }
      if (/^\s*---\s*$/.test(line)) {
        html += "<hr/>";
        continue;
      }
      if (/^\s*\|.*\|\s*$/.test(line)) {
        if (inList) { html += "</ul>"; inList = false; }
        var rows = [];
        while (li2 < lines.length && /^\s*\|.*\|\s*$/.test(lines[li2])) {
          rows.push(lines[li2].trim());
          li2++;
        }
        li2--;
        html += mdTable(rows);
        continue;
      }
      if (/^\s*>\s?/.test(line)) {
        html += "<blockquote>" + mdInline(line.replace(/^\s*>\s?/, "")) + "</blockquote>";
        continue;
      }
      var li = /^\s*[-*]\s+(.*)$/.exec(line);
      if (li) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += "<li>" + mdInline(li[1]) + "</li>";
        continue;
      }
      if (inList) { html += "</ul>"; inList = false; }
      if (line.trim()) html += "<p>" + mdInline(line) + "</p>";
    }
    if (inList) html += "</ul>";
    out += html;
  });
  return out;
}

function mdTable(rows) {
  var cells = function (row) {
    return row.replace(/^\|/, "").replace(/\|$/, "").split("|").map(function (c) { return c.trim(); });
  };
  if (rows.length < 2) return "<p>" + mdInline(rows.join(" ")) + "</p>";
  var head = cells(rows[0]);
  var body = rows.slice(1).filter(function (r) { return !/^[\s|:-]+$/.test(r); });
  var out = "<table class='qvq-md-table'><thead><tr>";
  head.forEach(function (c) { out += "<th>" + mdInline(c) + "</th>"; });
  out += "</tr></thead><tbody>";
  body.forEach(function (r) {
    out += "<tr>";
    cells(r).forEach(function (c) { out += "<td>" + mdInline(c) + "</td>"; });
    out += "</tr>";
  });
  return out + "</tbody></table>";
}
