const TRANSLATIONS = {
    ar: {
        "جامعة حائل": "University of Hail",
        "نظام الحضور الذكي": "Smart Attendance System",
        "نظام الحضور والغياب": "Attendance Management System",
        "تسجيل الخروج": "Logout",
        "العودة للوحة الأدمن": "Back to Dashboard",
        "المدير العام": "Administrator",
        "الدكاترة المسجلون": "Registered Doctors",
        "الطلاب المسجلون": "Registered Students",
        "المقررات النشطة": "Active Courses",
        "محاولات احتيال": "Spoof Attempts",
        "في النظام": "In system",
        "مسجّل بيومتري": "Biometrically registered",
        "هذا الفصل": "This semester",
        "هذا الأسبوع": "This week",
        "مرحباً بك في لوحة التحكم": "Welcome to the Dashboard",
        "الأقسام الرئيسية": "Main Sections",
        "معلومات النظام": "System Information",
        "روابط سريعة": "Quick Links",
        "سجلات أنشطة النظام": "System Activity Logs",
        "الاحتيال يظهر أولاً": "Spoof attempts shown first",
        "تسجيلات ناجحة": "Successful Records",
        "مسجّل بنجاح": "Successfully recorded",
        "حضور مكرر": "Duplicate Attendance",
        "طالب مسجّل مسبقاً": "Student already registered",
        "تسجيل مكرر": "Duplicate Registration",
        "أحداث أخرى": "Other Events",
        "الطالب / الجهة": "Student / Entity",
        "الإجراء": "Action",
        "المقرر / القاعة": "Course / Room",
        "التفاصيل": "Details",
        "التوقيت": "Timestamp",
        "الكل": "All",
        "حضور": "Attendance",
        "مكرر": "Duplicate",
        "تحليل Spoof": "Spoof Analysis",
        "حذف المحدد": "Delete Selected",
        "لا توجد سجلات": "No records found",
        "جاري تحميل السجلات...": "Loading records...",
        "القاعة": "Room",
        "تسجيل الحضور": "Record Attendance",
        "تسجيل الانصراف": "Record Checkout",
        "حاضر": "Present",
        "متأخر": "Late",
        "انصراف": "Checkout",
        "تحذير: محاولة احتيال!": "Warning: Spoof Attempt!",
        "ضع وجهك الحقيقي أمام الكاميرا": "Place your real face in front of the camera",
        "تم تسجيل هذه المحاولة في النظام": "This attempt has been recorded",
        "حسناً — سأضع وجهي": "OK — I will place my face"
    }
};

const I18N = {
    currentLang: localStorage.getItem("lang") || "ar",
    t(key) {
        if (this.currentLang === "en") return TRANSLATIONS.ar[key] || key;
        return key;
    },
    toggle() {
        this.currentLang = this.currentLang === "ar" ? "en" : "ar";
        localStorage.setItem("lang", this.currentLang);
        this.apply();
    },
    apply() {
        const isEn = this.currentLang === "en";
        document.documentElement.lang = this.currentLang;
        document.documentElement.dir  = isEn ? "ltr" : "rtl";
        document.querySelectorAll("[data-i18n]").forEach(el => {
            const key = el.getAttribute("data-i18n");
            el.textContent = isEn ? (TRANSLATIONS.ar[key] || key) : key;
        });
        document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
            const key = el.getAttribute("data-i18n-placeholder");
            el.placeholder = isEn ? (TRANSLATIONS.ar[key] || key) : key;
        });
        const btn = document.getElementById("langToggle");
        if (btn) btn.textContent = isEn ? "🌐 عربي" : "🌐 English";
    },
    init() { this.apply(); }
};

document.addEventListener("DOMContentLoaded", () => I18N.init());
