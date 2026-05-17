import qrcode

url = "https://compliance.keepyourcontracts.com/ui/intake.html"

qr = qrcode.QRCode(
    version=4,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=12,
    border=2,
)

qr.add_data(url)
qr.make(fit=True)

img = qr.make_image(fill_color="black", back_color="white")

img.save(r"ui\assets\qr\kyc_upload_qr.png")

print("QR CREATED:")
print(url)
