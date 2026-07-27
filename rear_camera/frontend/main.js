function sendValue(value) {
  Streamlit.setComponentValue(value);
}

function onRender(event) {
  if (window.rendered) return;

  const { height } = event.detail.args;
  const video = document.getElementById("video");
  const canvas = document.getElementById("canvas");
  const container = document.getElementById("container");

  const constraints = { facingMode: "environment", advanced: [{ focusMode: "continuous" }] };
  navigator.mediaDevices
    .getUserMedia({ video: constraints })
    .then(function (stream) {
      video.srcObject = stream;
      video.play();
      video.addEventListener("loadedmetadata", function () {
        // Size the iframe to the actual video height + the hint line.
        Streamlit.setFrameHeight(container.offsetHeight + 34);
      });
    })
    .catch(function (err) {
      console.log("camera error: " + err);
    });

  function takePicture() {
    const track = video.srcObject && video.srcObject.getVideoTracks()[0];
    if (!track) return;
    const s = track.getSettings();
    const w = s.width || video.videoWidth;
    const h = s.height || video.videoHeight;
    canvas.width = w;
    canvas.height = h;
    canvas.getContext("2d").drawImage(video, 0, 0, w, h);
    sendValue(canvas.toDataURL("image/png"));
  }

  video.addEventListener("click", takePicture);
  Streamlit.setFrameHeight(height || 460); // initial; refined on loadedmetadata
  window.rendered = true;
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight(460);
