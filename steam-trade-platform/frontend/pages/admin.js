import Head from 'next/head'
import { useEffect, useState } from 'react'
import axios from 'axios'

export default function Admin() {
  const [user, setUser] = useState(null)
  const [users, setUsers] = useState([])
  const [bots, setBots] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchData() {
      try {
        const userRes = await axios.get('http://localhost:4000/api/user', { withCredentials: true })
        setUser(userRes.data.user)
        if (userRes.data.user && userRes.data.user.isAdmin) {
          const usersRes = await axios.get('http://localhost:4000/api/admin/users', { withCredentials: true })
          setUsers(usersRes.data)
          const botsRes = await axios.get('http://localhost:4000/api/admin/bots', { withCredentials: true })
          setBots(botsRes.data)
        }
      } catch (err) {
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    fetchData()
  }, [])

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-pirateBlack text-pirateGold">
        <p>Loading...</p>
      </main>
    )
  }

  if (!user || !user.isAdmin) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-pirateBlack text-pirateGold">
        <p>Access denied. Admins only.</p>
      </main>
    )
  }

  return (
    <>
      <Head>
        <title>Admin Panel - Pirate Steam Trade Platform</title>
      </Head>
      <main className="min-h-screen bg-pirateBlack text-pirateGold p-8 font-pirate">
        <h1 className="text-4xl mb-6">Admin Panel</h1>
        <section className="mb-8">
          <h2 className="text-2xl mb-4">Users</h2>
          <ul>
            {users.map((u) => (
              <li key={u._id}>
                {u.personaName} - SteamID: {u.steamId} - Admin: {u.isAdmin ? 'Yes' : 'No'}
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h2 className="text-2xl mb-4">Bots</h2>
          <ul>
            {bots.map((bot) => (
              <li key={bot._id}>
                {bot.personaName} - SteamID: {bot.steamId} - Status: {bot.status}
              </li>
            ))}
          </ul>
        </section>
      </main>
    </>
  )
}
