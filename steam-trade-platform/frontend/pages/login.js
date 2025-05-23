import Head from 'next/head'

export default function Login() {
  return (
    <>
      <Head>
        <title>Login - Pirate Steam Trade Platform</title>
      </Head>
      <main className="min-h-screen flex flex-col items-center justify-center bg-pirateBlack text-pirateGold p-8">
        <h1 className="text-4xl mb-8 font-pirate">Login</h1>
        <a
          href="http://localhost:4000/auth/steam"
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded text-white font-semibold transition"
        >
          Login with Steam
        </a>
      </main>
    </>
  )
}
