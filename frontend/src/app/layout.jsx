import '../styles.css'

export const metadata = {
  title: 'HemoSense AI — Anemia Screening',
  description:
    'Estimate hemoglobin from a photo of the eye with fuzzy-logic colour correction, CNN regression and dietary intelligence.',
  icons: { icon: '/favicon.svg' },
}

export const viewport = {
  themeColor: '#be123c',
}

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  )
}
