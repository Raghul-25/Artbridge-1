import razorpay

key_id = "rzp_test_Sf0mFUZaFz6IJz"
key_secret = "tbe2Zb0OdbDiQuJQZEA2vXjh"
client = razorpay.Client(auth=(key_id, key_secret))

order = client.order.create(
    {
        "amount": 1000,
        "currency": "INR",
        "payment_capture": "1",
    }
)
print(order)
