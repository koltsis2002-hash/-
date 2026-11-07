(function () {
  var button = document.getElementById("print-now");
  if (button) button.addEventListener("click", function () { window.print(); });
  window.addEventListener("load", function () {
    (document.fonts ? document.fonts.ready : Promise.resolve()).then(function () {
      setTimeout(function () { window.print(); }, 250);
    });
  });
})();
