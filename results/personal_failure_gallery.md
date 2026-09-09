# Failure gallery

## tesseract (4 documents with at least one miss)

### train_0487

- image: `data/personal/images/train_0487.jpg`
- merchant [MISS]: gt='SANYU STATIONERY SHOP' pred='SANYO ST. ATIONERY SHOP 3833G, JALAN SETIA INDAH X ,UL3/4' cer=1.762
- date [MISS]: gt='18/09/2017' pred=None cer=1.000
- total [MISS]: gt='12.40' pred=None cer=1.000

### train_0168

- image: `data/personal/images/train_0168.jpg`
- merchant [MISS]: gt="KING'S CONFECTIONERY S/B" pred='KING’S CONFECTIONERY §/B 273500-U (KSB)' cer=0.708
- date [MISS]: gt='11/03/18' pred=None cer=1.000
- total [MISS]: gt='25.15' pred='1.42' cer=0.800

### train_0014

- image: `data/personal/images/train_0014.jpg`
- merchant [MISS]: gt='ASIA MART' pred='A MART' cer=0.333
- date [MISS]: gt='22/12/2017' pred=None cer=1.000
- total [MISS]: gt='32.70' pred='31.03' cer=0.600

### train_0317

- image: `data/personal/images/train_0317.jpg`
- merchant [MISS]: gt="WESTERN 'EASTERN' STATIONERY SDN. BHD" pred='WESTERN ‘EASTERN STeTLONERY SON. BHD' cer=0.135
- date [ok]: gt='16-04-2018' pred='16-04-2018' cer=0.000
- total [MISS]: gt='5.00' pred=None cer=1.000

## easyocr (5 documents with at least one miss)

### train_0168

- image: `data/personal/images/train_0168.jpg`
- merchant [MISS]: gt="KING'S CONFECTIONERY S/B" pred="KING'S CONFECTIONERY S/B'273500-U (KSB)" cer=0.625
- date [MISS]: gt='11/03/18' pred=None cer=1.000
- total [MISS]: gt='25.15' pred='1.42' cer=0.800

### train_0317

- image: `data/personal/images/train_0317.jpg`
- merchant [MISS]: gt="WESTERN 'EASTERN' STATIONERY SDN. BHD" pred="WESTERN 'EASTERN ST T [ ONERY" cer=0.378
- date [MISS]: gt='16-04-2018' pred=None cer=1.000
- total [MISS]: gt='5.00' pred=None cer=1.000

### train_0014

- image: `data/personal/images/train_0014.jpg`
- merchant [ok]: gt='ASIA MART' pred='ASIA MART' cer=0.000
- date [MISS]: gt='22/12/2017' pred=None cer=1.000
- total [MISS]: gt='32.70' pred='31.03' cer=0.600

### train_0487

- image: `data/personal/images/train_0487.jpg`
- merchant [ok]: gt='SANYU STATIONERY SHOP' pred='SANYU STATIONERY SHOP' cer=0.000
- date [MISS]: gt='18/09/2017' pred=None cer=1.000
- total [MISS]: gt='12.40' pred='0.70' cer=0.600

### train_0497

- image: `data/personal/images/train_0497.jpg`
- merchant [ok]: gt='SANYU STATIONERY SHOP' pred='SANYU STATIONERY SHOP' cer=0.000
- date [ok]: gt='08/07/2017' pred='08/07/2017' cer=0.000
- total [MISS]: gt='8.70' pred='0.49' cer=0.750

## vlm-gemini (1 documents with at least one miss)

### train_0168

- image: `data/personal/images/train_0168.jpg`
- merchant [MISS]: gt="KING'S CONFECTIONERY S/B" pred="KING'S CONFECTIONERY" cer=0.167
- date [ok]: gt='11/03/18' pred='11/03/18' cer=0.000
- total [ok]: gt='25.15' pred='25.15' cer=0.000
