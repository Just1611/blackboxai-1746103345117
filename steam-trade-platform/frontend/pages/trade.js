import Head from 'next/head'
import { useEffect, useState } from 'react'
import axios from 'axios'

export default function Trade() {
  const [user, setUser] = useState(null)
  const [skins, setSkins] = useState([])
  const [users, setUsers] = useState([])
  const [toUserId, setToUserId] = useState('')
  const [offeredSkins, setOfferedSkins] = useState([])
  const [requestedSkins, setRequestedSkins] = useState([])

  useEffect(() => {
    async function fetchData() {
      try {
        const userRes = await axios.get('http://localhost:4000/api/user', { withCredentials: true })
        setUser(userRes.data.user)
        if (userRes.data.user) {
          const skinsRes = await axios.get('http://localhost:4000/api/skins', { withCredentials: true })
          setSkins(skinsRes.data)
          const usersRes = await axios.get('http://localhost:4000/api/admin/users', { withCredentials: true })
          setUsers(usersRes.data.filter(u => u._id !== userRes.data.user._id))
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
        <p>Please login to propose a trade.</p>
      </main>
    )
  }

  function toggleOfferedSkin(skinId) {
    setOfferedSkins((prev) =>
      prev.includes(skinId) ? prev.filter((id) => id !== skinId) : [...prev, skinId]
    )
  }

  function toggleRequestedSkin(skinId) {
    setRequestedSkins((prev) =>
      prev.includes(skinId) ? prev.filter((id) => id !== skinId) : [...prev, skinId]
    )
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!toUserId || offeredSkins.length === 0 || requestedSkins.length === 0) {
      alert('Please select a user and at least one skin to offer and request.')
      return
    }
    try {
      await axios.post(
        'http://localhost:4000/api/tradeoffers',
        { toUserId, offeredSkins, requestedSkins },
        { withCredentials: true }
      )
      alert('Trade offer sent!')
      setToUserId('')
      setOfferedSkins([])
      setRequestedSkins([])
    } catch (err) {
      console.error(err)
      alert('Failed to send trade offer.')
    }
  }

  return (
    <>
      <Head>
        <title>Propose Trade - Pirate Steam Trade Platform</title>
      </Head>
      <main className="min-h-screen bg-pirateBlack text-pirateGold p-8 font-pirate">
        <h1 className="text-4xl mb-6">Propose a Trade</h1>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="toUser" className="block mb-2">
              Select User to Trade With
            </label>
            <select
              id="toUser"
              value={toUserId}
              onChange={(e) => setToUserId(e.target.value)}
              className="bg-pirateGold bg-opacity-20 p-2 rounded w-full"
            >
              <option value="">-- Select User --</option>
              {users.map((u) => (
                <option key={u._id} value={u._id}>
                  {u.personaName}
                </option>
              ))}
            </select>
          </div>
          <div>
            <h2 className="mb-2">Your Skins to Offer</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {skins.map((skin) => (
                <div
                  key={skin._id}
                  className={`p-2 border rounded cursor-pointer ${
                    offeredSkins.includes(skin._id) ? 'border-green-500' : 'border-transparent'
                  }`}
                  onClick={() => toggleOfferedSkin(skin._id)}
                >
                  <img src={skin.imageUrl} alt={skin.name} className="w-full h-24 object-cover rounded" />
                  <p className="text-center">{skin.name}</p>
                </div>
              ))}
            </div>
          </div>
          <div>
            <h2 className="mb-2">Skins You Want to Receive</h2>
            <textarea
              placeholder="Enter skin names or IDs you want to receive, separated by commas"
              value={requestedSkins.join(',')}
              onChange={(e) => setRequestedSkins(e.target.value.split(',').map(s => s.trim()))}
              className="w-full p-2 rounded bg-pirateGold bg-opacity-20"
            />
          </div>
          <button
            type="submit"
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 rounded text-white font-semibold transition"
          >
            Send Trade Offer
          </button>
        </form>
      </main>
    </>
  )
}
