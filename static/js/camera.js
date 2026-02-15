// =========================
// camera.js (FULL)
// =========================
const video = document.getElementById("video");
const sessionEl = document.getElementById("session"); // لازم يكون موجود في الصفحة
const msgEl = document.getElementById("msg"); // اختياري (لو عندك مكان رسائل)

// إعدادات الالتقاط
const CAPTURE_W = 320;
const CAPTURE_H = 240;
const JPEG_QUALITY = 0.9;

// تحسين الإضاءة (فلتر سريع)
const FILTER = "brightness(1.25) contrast(1.15) saturate(1.08)";

// تحسين بكسلات (أقوى شوي)
const PIXEL_BRIGHTNESS = 25; // + يفتح (جرّب 15-40)
const PIXEL_CONTRAST = 1.12; // >1 يزيد التباين (جرّب 1.05-1.25)

// منع تكرار الطلب
let busy = false;

// تشغيل الكاميرا
async function startCamera() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: {
        width: { ideal: 640 },
        height: { ideal: 480 },
        facingMode: "user"
        // ملاحظة: brightness/contrast غالباً ما تُحترم في المتصفحات
      },
      audio: false
    });

    video.srcObject = stream;

    // انتظر الفيديو يشتغل
    await new Promise((resolve) => {
      video.onloadedmetadata = () => resolve();
    });

    video.play();
    logMsg("✅ الكاميرا شغالة");
  } catch (err) {
    console.error(err);
    alert("❌ لم يتم تشغيل الكاميرا. تأكد من السماح للكاميرا من المتصفح.");
  }
}

function logMsg(t) {
  if (msgEl) msgEl.textContent = t;
  // إذا ما عندك msgEl، تجاهل
}

// تحسين البكسلات (رفع إضاءة + تباين)
function enhanceFrame(ctx, w, h) {
  const imgData = ctx.getImageData(0, 0, w, h);
  const d = imgData.data;

  const b = PIXEL_BRIGHTNESS;
  const c = PIXEL_CONTRAST;

  for (let i = 0; i < d.length; i += 4) {
    // (value - 128) * contrast + 128 + brightness
    d[i]   = clamp((d[i]   - 128) * c + 128 + b); // R
    d[i+1] = clamp((d[i+1] - 128) * c + 128 + b); // G
    d[i+2] = clamp((d[i+2] - 128) * c + 128 + b); // B
    // alpha ثابت
  }

  ctx.putImageData(imgData, 0, 0);
}

function clamp(v) {
  v = Math.round(v);
  if (v < 0) return 0;
  if (v > 255) return 255;
  return v;
}

// التقاط صورة + إرسال
async function capture() {
  if (busy) return;
  if (!sessionEl || !sessionEl.value) {
    alert("اختر المحاضرة أولاً");
    return;
  }

  busy = true;
  try {
    const canvas = document.createElement("canvas");
    canvas.width = CAPTURE_W;
    canvas.height = CAPTURE_H;

    const ctx = canvas.getContext("2d", { willReadFrequently: true });

    // فلتر بصري سريع
    ctx.filter = FILTER;

    // رسم الفيديو
    ctx.drawImage(video, 0, 0, CAPTURE_W, CAPTURE_H);

    // تحسين بكسلات إضافي (يفيد بالظلام)
    enhanceFrame(ctx, CAPTURE_W, CAPTURE_H);

    // Base64 JPEG
    const dataURL = canvas.toDataURL("image/jpeg", JPEG_QUALITY);

    // إرسال للسيرفر
    const res = await fetch("/student/attendance", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionEl.value,
        image: dataURL
      })
    });

    const data = await res.json();

    // عرض رسالة
    if (data && data.message) {
      logMsg(data.message);
      // لو تبي alert مثل كودك القديم:
      // alert(data.message);
    } else {
      logMsg("تم الإرسال ✅");
    }

  } catch (e) {
    console.error(e);
    alert("❌ صار خطأ أثناء الالتقاط/الإرسال");
  } finally {
    busy = false;
  }
}

// (اختياري) تشغيل تلقائي كل ثانية بدل الضغط
let autoTimer = null;
function startAutoCapture(intervalMs = 1200) {
  stopAutoCapture();
  autoTimer = setInterval(() => {
    capture();
  }, intervalMs);
}

function stopAutoCapture() {
  if (autoTimer) clearInterval(autoTimer);
  autoTimer = null;
}

// شغل الكاميرا عند فتح الصفحة
startCamera();

// خلي الدوال متاحة للـ HTML (لو زر onclick="capture()")
window.capture = capture;
window.startAutoCapture = startAutoCapture;
window.stopAutoCapture = stopAutoCapture;
