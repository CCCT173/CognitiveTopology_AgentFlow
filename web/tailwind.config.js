/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // 品牌蓝
        brand: {
          50: '#F0F5FF',
          100: '#D6E4FF',
          200: '#ADC8FF',
          300: '#84ABFF',
          400: '#5A8FFF',
          500: '#2970FF',
          600: '#155EEB',
          700: '#0D52D8',
          800: '#0A44B4',
          900: '#083A96',
        },
        // 背景色
        app: '#F7F8FA',
        sidebar: '#FFFFFF',
        card: '#FFFFFF',
        hover: '#F3F4F6',
        active: '#EAECEF',
        subtle: '#F9FAFB',
        // 文字
        primary: '#0F1528',
        secondary: '#4B546C',
        tertiary: '#9AA2B8',
        placeholder: '#AEB5C8',
        disabled: '#D0D5DC',
        // 状态色
        success: '#079455',
        danger: '#D92D20',
        warning: '#DC6803',
      },
      fontFamily: {
        sans: ['PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['10px', '14px'],
        xs: ['11px', '16px'],
        sm: ['12px', '18px'],
        base: ['13px', '20px'],
        lg: ['14px', '22px'],
        xl: ['16px', '24px'],
        '2xl': ['18px', '28px'],
        '3xl': ['20px', '30px'],
      },
      borderRadius: {
        xs: '4px',
        sm: '6px',
        md: '8px',
        lg: '12px',
        xl: '16px',
        '2xl': '20px',
      },
      boxShadow: {
        xs: '0 1px 2px 0 rgb(16 24 40 / 0.05)',
        sm: '0 1px 2px 0 rgb(16 24 40 / 0.06), 0 1px 3px 0 rgb(16 24 40 / 0.1)',
        md: '0 4px 6px -2px rgb(16 24 40 / 0.06), 0 8px 24px 0 rgb(16 24 40 / 0.04)',
        lg: '0 8px 16px -4px rgb(16 24 40 / 0.08), 0 16px 48px 0 rgb(16 24 40 / 0.06)',
        xl: '0 12px 24px -8px rgb(16 24 40 / 0.12), 0 24px 64px 0 rgb(16 24 40 / 0.08)',
      },
      animation: {
        'fadeIn': 'fadeIn 0.3s ease-out',
        'slideUp': 'slideUp 0.3s ease-out',
        'pulse-soft': 'pulseSoft 2s ease-in-out infinite',
        'spin': 'spin 1s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
      },
    },
  },
  plugins: [],
}
