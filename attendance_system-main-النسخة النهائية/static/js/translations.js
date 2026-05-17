/**
 * translations.js
 * نظام الترجمة العربي/الإنجليزي
 * ضعه في: /static/js/translations.js
 */

const TRANSLATIONS = {
    ar: {
        // عام
        'جامعة حائل': 'University of Hail',
        'نظام الحضور الذكي': 'Smart Attendance System',
        'نظام الحضور والغياب': 'Attendance Management System',
        'تسجيل الخروج': 'Logout',
        'العودة للوحة الأدمن': 'Back to Dashboard',
        'جاري التحميل': 'Loading...',
        'لا توجد بيانات': 'No data available',

        // Dashboard
        'لوحة تحكم الإدارة': 'Admin Dashboard',
        'مرحباً بك في لوحة التحكم': 'Welcome to the Dashboard',
        'إدارة شاملة لنظام الحضور الذكي': 'Comprehensive Smart Attendance Management',
        'الأقسام الرئيسية': 'Main Sections',
        'الدكاترة المسجلون': 'Registered Doctors',
        'الطلاب المسجلون': 'Registered Students',
        'المقررات النشطة': 'Active Courses',
        'محاولات احتيال': 'Spoof Attempts',
        'في النظام': 'In system',
        'مسجّل بيومتري': 'Biometrically registered',
        'هذا الفصل': 'This semester',
        'هذا الأسبوع': 'This week',
        'المدير العام': 'Administrator',
        'معلومات النظام': 'System Information',
        'روابط سريعة': 'Quick Links',
        'فتح الكشك': 'Open Kiosk',
        'بوابة الدكتور': 'Doctor Portal',
        'بوابة الطالب': 'Student Portal',
        'تصدير CSV': 'Export CSV',

        // Nav cards
        'الطلاب': 'Students',
        'تسجيل وجوه الطلاب بيومترياً وإدارة بياناتهم في النظام': 'Register student faces biometrically and manage their data',
        'إدارة الطلاب': 'Manage Students',
        'الدكاترة': 'Doctors',
        'إضافة الدكاترة وتعديل بياناتهم وإدارة صلاحيات الدخول': 'Add doctors, edit their data and manage access permissions',
        'إدارة الدكاترة': 'Manage Doctors',
        'المقررات والشعب': 'Courses & Sections',
        'إضافة المقررات والجداول الدراسية وتحديد القاعات وأوقات المحاضرات': 'Add courses, schedules, rooms and lecture times',
        'إدارة المقررات': 'Manage Courses',
        'سجل الحضور': 'Attendance Record',
        'عرض جميع سجلات الحضور والانصراف مع إمكانية التصفية والتصدير': 'View all attendance records with filtering and export options',
        'عرض الحضور': 'View Attendance',
        'اعتراضات الغياب': 'Absence Appeals',
        'مراجعة اعتراضات الطلاب على الغياب والبت فيها بالقبول أو الرفض': 'Review student absence appeals and approve or reject them',
        'إدارة الاعتراضات': 'Manage Appeals',
        'سجلات النظام': 'System Logs',
        'مراقبة جميع الأنشطة ومحاولات الاحتيال وتحليل نتائج الـ Anti-Spoofing': 'Monitor all activities, spoof attempts and Anti-Spoofing results',
        'عرض السجلات': 'View Logs',

        // Logs page
        'سجلات أنشطة النظام': 'System Activity Logs',
        'الاحتيال يظهر أولاً': 'Spoof attempts shown first',
        'تحديث تلقائي كل 30 ثانية': 'Auto-refresh every 30 seconds',
        'تسجيلات ناجحة': 'Successful Records',
        'مسجّل بنجاح': 'Successfully recorded',
        'حضور مكرر': 'Duplicate Attendance',
        'طالب مسجّل مسبقاً': 'Student already registered',
        'تسجيل مكرر': 'Duplicate Registration',
        'وجه مسجّل من قبل': 'Face already registered',
        'أحداث أخرى': 'Other Events',
        'نشاطات النظام': 'System activities',
        'الطالب / الجهة': 'Student / Entity',
        'الإجراء': 'Action',
        'المقرر / القاعة': 'Course / Room',
        'التفاصيل': 'Details',
        'تحليل Anti-Spoofing': 'Anti-Spoofing Analysis',
        'التوقيت': 'Timestamp',
        'ابحث بالاسم أو الرقم الجامعي أو المقرر...': 'Search by name, student ID or course...',
        'تصدير CSV': 'Export CSV',
        'تحليل Spoof': 'Spoof Analysis',
        'حذف المحدد': 'Delete Selected',
        'الكل': 'All',
        'احتيال': 'Spoof',
        'حضور': 'Attendance',
        'مكرر': 'Duplicate',
        '⚠️ جهة مجهولة': '⚠️ Unknown Entity',
        'لم يتم التعرف على الهوية': 'Identity not recognized',
        'لا توجد سجلات': 'No records found',
        'جاري تحميل السجلات...': 'Loading records...',

        // Badges
        '✅ تسجيل حضور': '✅ Attendance Recorded',
        '🔄 حضور مكرر': '🔄 Duplicate Attendance',
        '🚫 تسجيل مكرر': '🚫 Duplicate Registration',
        '🚨 محاولات احتيال': '🚨 Spoof Attempts',
        '🚨 محاولة احتيال': '🚨 Spoof Attempt',
        '👤 تسجيل طالب': '👤 Student Registered',
        '🔑 تغيير كلمة مرور': '🔑 Password Changed',

        // Kiosk
        'كشك الحضور': 'Attendance Kiosk',
        'القاعة': 'Room',
        'تسجيل الحضور': 'Record Attendance',
        'تسجيل الانصراف': 'Record Checkout',
        'انتهت المحاضرة': 'Lecture Ended',
        'بانتظار المحاضرة': 'Waiting for Lecture',
        'جاري التهيئة': 'Initializing',
        'ضع وجهك داخل الإطار': 'Place your face in the frame',
        'جاهز — ضع وجهك أمام الكاميرا': 'Ready — place your face in front of the camera',
        'الكاميرا جاهزة': 'Camera ready',
        'حاضر': 'Present',
        'متأخر': 'Late',
        'انصراف': 'Checkout',
        'مسجل مسبقاً': 'Already registered',
        'وجه غير مسجل': 'Face not registered',
        'تحذير: محاولة احتيال!': 'Warning: Spoof Attempt!',
        'تم اكتشاف محاولة تسجيل حضور بصورة أو جهاز': 'A spoof attendance attempt was detected via photo or device',
        'ضع وجهك الحقيقي أمام الكاميرا': 'Place your real face in front of the camera',
        'تم تسجيل هذه المحاولة في النظام': 'This attempt has been recorded in the system',
        'حسناً — سأضع وجهي': 'OK — I will place my face',

        // Time
        'دقيقة': 'minute',
        'أقل من دقيقة': 'Less than a minute',
        'إجمالي ناجح': 'Total successful',
        'Spoof Detected': 'Spoof Detected',
    }
};

// ==========================================
// نظام الترجمة
// ==========================================

const I18N = {
    currentLang: localStorage.getItem('lang') || 'ar',

    // ترجم نص واحد
    t(key) {
        if (this.currentLang === 'en') {
            return TRANSLATIONS.ar[key] || key;
        }
        // العربي هو الأصل
        return key;
    },

    // تبديل اللغة
    toggle() {
        this.currentLang = this.currentLang === 'ar' ? 'en' : 'ar';
        localStorage.setItem('lang', this.currentLang);
        this.apply();
    },

    // تطبيق الترجمة على الصفحة
    apply() {
        const isEn = this.currentLang === 'en';

        // اتجاه الصفحة
        document.documentElement.lang = this.currentLang;
        document.documentElement.dir  = isEn ? 'ltr' : 'rtl';

        // كل العناصر التي فيها data-i18n
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (isEn) {
                el.textContent = TRANSLATIONS.ar[key] || key;
            } else {
                el.textContent = key;
            }
        });

        // كل العناصر التي فيها data-i18n-placeholder
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (isEn) {
                el.placeholder = TRANSLATIONS.ar[key] || key;
            } else {
                el.placeholder = key;
            }
        });

        // تحديث زر اللغة
        const btn = document.getElementById('langToggle');
        if (btn) {
            btn.textContent = isEn ? '🌐 عربي' : '🌐 English';
            btn.title = isEn ? 'Switch to Arabic' : 'Switch to English';
        }
    },

    // تهيئة عند تحميل الصفحة
    init() {
        this.apply();
    }
};

// تشغيل عند تحميل الصفحة
document.addEventListener('DOMContentLoaded', () => I18N.init());
