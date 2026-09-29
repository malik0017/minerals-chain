/* Batch M3 — picking a catalog product fills the spec table from the
   Quality Specification master (GET /catalog/specs). Markup contract:
   <select data-spec-prefill="TABLE_ID" data-fill-name="INPUT_ID?"> and the
   spec_editor macro's table + <template id="TABLE_ID-tpl">. */
(function () {
  function fill(select) {
    var id = select.getAttribute("data-spec-prefill");
    var table = document.getElementById(id), tpl = document.getElementById(id + "-tpl");
    if (!select.value || !table || !tpl) return;
    fetch("/catalog/specs?product_master_id=" + encodeURIComponent(select.value), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        var nameInput = document.getElementById(select.getAttribute("data-fill-name") || "");
        if (nameInput && !nameInput.value && data.product) nameInput.value = data.product.name;
        if (!data.rows.length) return;
        var body = table.querySelector("tbody");
        var hasValues = Array.prototype.some.call(body.querySelectorAll("input[name$='_param']"), function (i) { return i.value; });
        if (hasValues && !confirm("Replace the current specification rows with the catalog ranges?")) return;
        body.innerHTML = "";
        data.rows.forEach(function (row) {
          var frag = tpl.content.cloneNode(true);
          var set = function (suffix, v) { var el = frag.querySelector("input[name$='_" + suffix + "']"); if (el) el.value = v; };
          set("pid", row.parameter_id); set("param", row.parameter); set("min", row.min); set("max", row.max);
          set("unit", row.unit); set("method", row.test_method);
          body.appendChild(frag);
        });
      });
  }
  document.addEventListener("change", function (e) {
    if (e.target && e.target.matches("select[data-spec-prefill]")) fill(e.target);
  });
})();
