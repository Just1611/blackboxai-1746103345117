import Head from 'next/head'
import { useEffect, useState } from 'react'
import axios from 'axios'
import Link from 'next/link'

export default function Dashboard() {
  const [user, setUser] = useState(null)
  const [skins, setSkins] = useState([])
  const [tradeOffers, setTradeOffers] = useState([])

  useEffect(() => {
    async function fetchData() {
      try {
        const userRes = await axios.get('http://localhost:4000/api/user', { withCredentials: true })
        setUser(userRes.data.user)
        if (userRes.data.user) {
          const skinsRes = await axios.get('http://localhost:4000/api/skins', { withCredentials: true })
          setSkins(skinsRes.data)
          const offersRes = await axios.get('http://localhost:4000/api/tradeoffers', { withCredentials: true })
          setTradeOffers(offersRes.data)
        }
      } catch (err) {
        console.error(err)
      }
    }
    fetchData()
  }, [])

  if (!user) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-pirateBlack text-pirateGold">
        <p>Please login to view your dashboard.</p>
      </main>
    )
  }

  return (
    <>
      <Head>
        <title>Dashboard - Pirate Steam Trade Platform</title>
      </Head>
      <main className="min-h-screen bg-pirateBlack text-pirateGold p-8 font-pirate">
        <h1 className="text-4xl mb-6">Welcome, {user.personaName}</h1>
        <section className="mb-8">
          <h2 className="text-2xl mb-4">Your Skins</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {skins.map((skin) => (
              <div key={skin._id} className="bg-pirateGold bg-opacity-20 p-4 rounded">
                <img src={skin.imageUrl} alt={skin.name} className="w-full h-32 object-cover rounded mb-2" />
                <p>{skin.name}</p>
                <p className="text-sm italic">{skin.game}</p>
              </div>
            ))}
          </div>
        </section>
        <section className="mb-8">
          <h2 className="text-2xl mb-4">Trade Offers</h2>
          <div>
            {tradeOffers.length === 0 && <p>No trade offers.</p>}
            {tradeOffers.map((offer) => (
              <div key={offer._id} className="border border-pirateGold p-4 rounded mb-4">
                <p>
                  From: {offer.fromUser.personaName} To: {offer.toUser.personaName}
                </p>
                <p>Status: {offer.status}</p>
                <div className="flex space-x-4 mt-2">
                  <div>
                    <h3>Offered Skins</h3>
                    <ul>
                      {offer.offeredSkins.map((skin) => (
                        <li key={skin._id}>{skin.name}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <h3>Requested Skins</h3>
                    <ul>
                      {offer.requestedSkins.map((skin) => (
                        <li key={skin._id}>{skin.name}</li>
                      ))}
                    </ul>
                  </div>
                </div>
                {offer.status === 'pending' && offer.toUser._id === user._id && (
                  <div className="mt-2">
                    <button
                      className="mr-2 px-4 py-2 bg-green-600 rounded hover:bg-green-700"
                      onClick={() => handleAccept(offer._id)}
                    >
                      Accept
                    </button>
                    <button
                      className="px-4 py-2 bg-red-600 rounded hover:bg-red-700"
                      onClick={() => handleReject(offer._id)}
                    >
                      Reject
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
        <Link href="/trade">
          <a className="inline-block px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded text-white font-semibold transition">
            Propose a Trade
          </a>
        </Link>
      </main>
    </>
  )

  async function handleAccept(offerId) {
    try {
      await axios.post(`http://localhost:4000/api/tradeoffers/${offerId}/accept`, {}, { withCredentials: true })
      const offersRes = await axios.get('http://localhost:4000/api/tradeoffers', { withCredentials: true })
      setTradeOffers(offersRes.data)
    } catch (err) {
      console.error(err)
    }
  }

  async function handleReject(offerId) {
    try {
      await axios.post(`http://localhost:4000/api/tradeoffers/${offerId}/reject`, {}, { withCredentials: true })
      const offersRes = await axios.get('http://localhost:4000/api/tradeoffers', { withCredentials: true })
      setTradeOffers(offersRes.data)
    } catch (err) {
      console.error(err)
    }
  }
}
