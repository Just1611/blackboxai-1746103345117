import Head from 'next/head'
import { motion } from 'framer-motion'

export default function Home() {
  return (
    <>
      <Head>
        <title>Pirate Steam Trade Platform</title>
        <meta name="description" content="Pirate futuristic Steam trade platform" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          href="https://fonts.googleapis.com/css2?family=Pirata+One&family=Inter&display=swap"
          rel="stylesheet"
        />
        <link
          rel="stylesheet"
          href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css"
        />
      </Head>
      <main className="min-h-screen bg-pirateBlack text-pirateGold font-pirate flex flex-col items-center justify-center p-8">
        <motion.h1
          className="text-6xl mb-4"
          initial={{ opacity: 0, y: -50 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
        >
          Pirate Steam Trade Platform
        </motion.h1>
        <p className="text-xl max-w-xl text-center font-sans">
          Welcome to the futuristic pirate-themed Steam trade platform.
        </p>
      </main>
    </>
  )
}
