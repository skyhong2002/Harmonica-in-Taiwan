(function () {
  const frame = document.querySelector("[data-public-calendar-embed]");
  const inputs = Array.from(document.querySelectorAll("[data-calendar-source]"));
  if (!frame || !inputs.length) return;

  const frameWrapper = frame.closest(".public-calendar-frame");
  const emptyState = frameWrapper?.querySelector(".public-calendar-empty");

  function updateCalendar() {
    const selected = inputs.filter((input) => input.checked);
    const isEmpty = selected.length === 0;
    frameWrapper?.classList.toggle("is-empty", isEmpty);
    if (emptyState) emptyState.hidden = !isEmpty;
    if (isEmpty) return;

    const url = new URL("https://calendar.google.com/calendar/embed");
    selected.forEach((input) => {
      url.searchParams.append("src", input.dataset.calendarId || "");
      url.searchParams.append("color", input.dataset.calendarColor || "#0B8043");
    });
    url.searchParams.set("ctz", "Asia/Taipei");
    url.searchParams.set("mode", "AGENDA");
    url.searchParams.set("showTitle", "0");
    url.searchParams.set("showNav", "1");
    url.searchParams.set("showDate", "1");
    url.searchParams.set("showPrint", "0");
    url.searchParams.set("showTabs", "0");
    url.searchParams.set("showCalendars", "0");
    url.searchParams.set("showTz", "0");

    const nextSrc = url.toString();
    if (frame.src !== nextSrc) frame.src = nextSrc;
  }

  inputs.forEach((input) => input.addEventListener("change", updateCalendar));
  updateCalendar();
})();
