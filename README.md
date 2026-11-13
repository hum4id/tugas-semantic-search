# Semantic Search & Vector Database

## Project Information

**Nama Project:**

Semantic Search Kuliner Nusantara

**Tema Dataset:**

Makanan dan minuman tradisional Indonesia (Kuliner Nusantara).

**Deskripsi Singkat:**

API pencarian berbasis makna untuk deskripsi kuliner Nusantara. Setiap deskripsi diubah menjadi embedding 384 dimensi menggunakan `paraphrase-multilingual-MiniLM-L12-v2`, disimpan di Qdrant beserta metadata (payload), lalu dicari menggunakan cosine similarity. Pengguna bisa mencari dengan kalimat bebas seperti "minuman yang cocok diminum ketika masuk angin" tanpa harus tahu nama makanannya.

## Cara Menjalankan

```bash
python -m venv venv
venv\Scripts\activate            # Windows
# source venv/bin/activate       # macOS / Linux
pip install -r requirements.txt
fastapi dev main.py
```

Buka `http://127.0.0.1:8000/docs`, jalankan `POST /index`, lalu `POST /search`.

Seluruh eksperimen di README ini dapat dijalankan ulang otomatis dengan `python experiments/run_experiments.py` (pastikan server lain sedang mati). Raw output-nya tersimpan di `experiments/results.json` dan `experiments/results.md`.

## Dataset

### Jumlah Data

36 data (`data.json`).

### Kategori yang Digunakan

| Kategori | Jumlah | Contoh |
|---|---|---|
| `makanan_utama` | 9 | Rendang, Gudeg, Ayam Taliwang |
| `sup_dan_soto` | 9 | Rawon, Soto Betawi, Sroto Sokaraja |
| `jajanan` | 9 | Mendoan, Klepon, Getuk |
| `minuman` | 9 | Wedang Jahe, Es Cendol, Bandrek |

Setiap data memiliki field `name`, `text`, `category`, dan `region`.

### Kenapa kalian memilih dataset tersebut?

Deskripsi makanan kaya akan sinonim dan parafrase (singkong = ubi kayu, lumer = meleleh, kuah = sup), sehingga cocok untuk menguji apakah pencarian benar-benar berbasis makna dan bukan sekadar kecocokan kata. Kategorinya juga saling berdekatan (misalnya `sup_dan_soto` dan `makanan_utama` sama-sama berisi daging), sehingga kelemahan retrieval lebih mudah terlihat.

## Tech Stack

- Python 3.12
- FastAPI (`fastapi[standard]`) + Pydantic untuk request body dan validasi
- SentenceTransformers dengan model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Qdrant (`qdrant-client`, local persistent mode di folder `qdrant_data/`) dengan distance metric COSINE
- httpx untuk script eksperimen

## Application Flow

```
Dataset -> Embedding -> Vector -> Qdrant
User Query -> Embedding -> Qdrant Search -> Top-K Results
```

**Penjelasan kalian:**

Saat `POST /index` dipanggil, aplikasi membaca 36 data dari `data.json`, lalu field `text` dari setiap data diubah menjadi vector berukuran 384 oleh model embedding. Collection lama dihapus dan dibuat ulang dengan ukuran vector 384 dan distance COSINE, kemudian setiap data disimpan sebagai satu point Qdrant berisi ID (index data, sehingga indexing ulang tidak menggandakan data), vector, dan payload.

Saat `POST /search` dipanggil, query pengguna diubah menjadi vector menggunakan model yang sama. Ini penting, karena vector query dan vector dokumen harus berada di ruang embedding yang sama agar bisa dibandingkan. Qdrant lalu menghitung cosine similarity antara vector query dan seluruh vector yang tersimpan, kemudian mengembalikan `top_k` point dengan skor tertinggi beserta payload-nya. Payload inilah yang ditampilkan sebagai `name`, `text`, `category`, `region`, dan `score`.

## Embedding Model

Model yang digunakan:

```
sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

### Menurut kalian, apa fungsi embedding model pada project ini?

Embedding model mengubah kalimat menjadi vector numerik (384 dimensi) sehingga kalimat dengan makna mirip berada berdekatan di ruang vector, walaupun kata-katanya berbeda. Contohnya, query "lauk daging yang awet karena dimasak sampai kering" tidak memuat kata "rendang", "santan", ataupun "kuahnya habis", tetapi tetap menempatkan Rendang di peringkat pertama (skor 0.6485). Model ini juga multilingual: query bahasa Inggris "spicy grilled chicken from Lombok" menemukan Ayam Taliwang yang dideskripsikan dalam bahasa Indonesia dengan skor 0.7926, skor tertinggi di seluruh eksperimen.

## Vector Database

### Apa fungsi Qdrant pada aplikasi kalian?

Qdrant menyimpan vector beserta payload secara persisten di folder `qdrant_data/`, sehingga embedding tidak perlu dihitung ulang setiap server dinyalakan. Qdrant juga melakukan pencarian nearest neighbor berdasarkan cosine similarity dan mendukung filter berdasarkan payload. Di aplikasi ini filter dipakai untuk parameter opsional `category`, misalnya `{"query": "...", "category": "minuman"}`.

### Apa saja data yang kalian simpan di payload?

`name`, `text`, `category`, dan `region`. `text` dan `category` wajib ditampilkan di hasil pencarian, `name` memudahkan membaca hasil, dan `category` sekaligus dipakai untuk filter.

## API Endpoint

| Method | Endpoint | Fungsi |
|---|---|---|
| GET | `/health` | Status server, model, ukuran vector, dan jumlah point di collection |
| POST | `/index` | Embedding seluruh dataset lalu menyimpannya ke Qdrant. Body opsional `{"recreate": true}` |
| POST | `/search` | Semantic search. Body: `query` (wajib), `top_k` (1-50, default 3), `category` (opsional) |

Error handling: `/search` mengembalikan 400 jika dataset belum di-index atau query kosong, dan 422 jika `top_k` di luar rentang. Pada pengujian, `{"query": "soto", "top_k": 0}` menghasilkan 422 dengan pesan `Input should be greater than or equal to 1`.

## Example Request

```json
POST /search
{
  "query": "sup berwarna hitam pekat dari Jawa Timur",
  "top_k": 3
}
```

## Example Response

```json
{
  "query": "sup berwarna hitam pekat dari Jawa Timur",
  "top_k": 3,
  "category_filter": null,
  "results": [
    {
      "id": 10,
      "name": "Rawon",
      "text": "Rawon adalah sup daging sapi berkuah hitam pekat karena menggunakan bumbu kluwek, disajikan dengan tauge pendek, telur asin, dan sambal.",
      "category": "sup_dan_soto",
      "region": "Jawa Timur",
      "score": 0.5612
    },
    {
      "id": 15,
      "name": "Coto Makassar",
      "text": "Coto Makassar adalah hidangan berkuah dari daging dan jeroan sapi dengan kuah kental yang diberi kacang tanah sangrai, disantap bersama ketupat.",
      "category": "sup_dan_soto",
      "region": "Sulawesi Selatan",
      "score": 0.4589
    },
    {
      "id": 12,
      "name": "Sroto Sokaraja",
      "text": "Sroto Sokaraja adalah soto berisi daging sapi atau ayam, ketupat, dan tauge yang kuahnya dicampur sambal kacang serta ditaburi kerupuk warna-warni.",
      "category": "sup_dan_soto",
      "region": "Banyumas, Jawa Tengah",
      "score": 0.4422
    }
  ]
}
```

## Experiment 1 - Semantic Search

Semua query dijalankan dengan `top_k = 3`. Total ada 7 query yang diuji; 5 query di bawah adalah query yang hasilnya relevan, sedangkan 2 query lainnya dibahas di Experiment 3.

### Query 1

**Query:** `sup berwarna hitam pekat dari Jawa Timur`

**Top Result:** Rawon (`sup_dan_soto`)

**Similarity Score:** 0.5612

**Menurut kalian apakah hasilnya relevan? Kenapa?**

Relevan. Query tidak menyebut "kluwek" maupun "rawon", tetapi frasa "hitam pekat" dan "Jawa Timur" cukup untuk menempatkan Rawon di posisi pertama dengan selisih cukup jauh dari peringkat kedua (0.4589). Menariknya, Sop Konro yang juga berkuah hitam dari kluwek tidak masuk top-3. Kemungkinan karena deskripsinya memakai "cokelat kehitaman", bukan "hitam pekat", dan berasal dari Sulawesi Selatan.

### Query 2

**Query:** `minuman yang cocok diminum ketika masuk angin`

**Top Result:** Wedang Jahe (`minuman`)

**Similarity Score:** 0.5184

**Menurut kalian apakah hasilnya relevan? Kenapa?**

Relevan. Kata "masuk angin" tidak ada di dataset; yang ada hanya "badan kurang fit" dan "cuaca dingin" di deskripsi Wedang Jahe. Model mampu menghubungkan keduanya. Ketiga hasil berkategori `minuman`, tetapi peringkat kedua (Kopi Tubruk, 0.4813) kurang tepat untuk masuk angin, dan skor ketiganya berdekatan (0.5184, 0.4813, 0.4796). Artinya model yakin "ini minuman", tetapi tidak terlalu yakin minuman yang mana.

### Query 3

**Query:** `olahan ikan dari Palembang yang dicocol saus asam`

**Top Result:** Pempek (`jajanan`)

**Similarity Score:** 0.6441

**Menurut kalian apakah hasilnya relevan? Kenapa?**

Relevan. Dataset menulis "Sumatera Selatan" dan "kuah cuko", bukan "Palembang" dan "saus asam", tetapi Pempek tetap peringkat pertama dengan selisih lebih dari 0.1 dari peringkat kedua (Cireng, 0.5397). Ini menunjukkan model memahami hubungan Palembang dengan Sumatera Selatan dan hubungan kuah cuko dengan saus asam.

### Query 4

**Query:** `lauk daging yang awet karena dimasak sampai kering`

**Top Result:** Rendang (`makanan_utama`)

**Similarity Score:** 0.6485

**Menurut kalian apakah hasilnya relevan? Kenapa?**

Relevan. "Awet" dan "sampai kering" adalah parafrase dari "awet disimpan" dan "hingga kuahnya habis". Peringkat dua dan tiga (Ayam Taliwang 0.6214, Tengkleng 0.5909) juga sama-sama hidangan daging, tetapi tidak memiliki ciri "awet". Skor peringkat 1 sampai 3 cukup rapat, sehingga hasil teratas benar tetapi pemisahnya tidak terlalu tegas.

### Query 5

**Query:** `spicy grilled chicken from Lombok`

**Top Result:** Ayam Taliwang (`makanan_utama`)

**Similarity Score:** 0.7926

**Menurut kalian apakah hasilnya relevan? Kenapa?**

Relevan, dan ini skor tertinggi di seluruh eksperimen walaupun query-nya berbahasa Inggris dan datasetnya berbahasa Indonesia. Model multilingual memetakan "spicy grilled chicken" ke "ayam ... dibakar ... sangat pedas". Peringkat kedua, Ayam Betutu (0.7161), juga ayam pedas, tetapi dari Bali dan dipanggang/dikukus, sehingga urutannya masuk akal.

## Experiment 2 - Top-K

Gunakan query yang sama.

### Query

`minuman tradisional yang disajikan hangat`

### Top-K = 1

**Actual Result:**

1. Wedang Uwuh (`minuman`), score 0.6131

### Top-K = 3

**Actual Result:**

1. Wedang Uwuh (`minuman`), score 0.6131
2. Wedang Jahe (`minuman`), score 0.5599
3. Bandrek (`minuman`), score 0.5547

### Top-K = 5

**Actual Result:**

1. Wedang Uwuh (`minuman`), score 0.6131
2. Wedang Jahe (`minuman`), score 0.5599
3. Bandrek (`minuman`), score 0.5547
4. Bajigur (`minuman`), score 0.4610
5. Sroto Sokaraja (`sup_dan_soto`), score 0.4555

### Apa perubahan yang kalian lihat ketika nilai Top-K diperbesar?

Top-K hanya menambah hasil di bagian bawah; urutan dan skor hasil sebelumnya tidak berubah sama sekali (Wedang Uwuh tetap 0.6131 di semua nilai K). Hal ini wajar karena Qdrant selalu mengurutkan berdasarkan skor, lalu memotong sebanyak K. Semakin besar K, skor hasil tambahan semakin rendah. Pada K=5, hasil ke-4 (Bajigur) masih relevan karena juga minuman hangat, tetapi hasil ke-5 adalah Sroto Sokaraja, yaitu soto dan bukan minuman. Padahal masih ada minuman hangat lain di dataset (Kopi Tubruk) yang tidak terambil.

Ada juga satu hal yang patut dicatat: peringkat pertama justru Wedang Uwuh, yang deskripsinya tidak memakai kata "hangat" sama sekali, sedangkan Wedang Jahe dan Bandrek yang jelas-jelas ditulis "minuman hangat" berada di bawahnya. Model tampaknya lebih menangkap konsep "minuman rempah tradisional" daripada atribut "hangat".

### Apakah menambah Top-K selalu membuat hasil pencarian menjadi lebih baik?

Tidak. Menambah K menaikkan recall (lebih banyak data relevan ikut terambil, misalnya Bajigur pada K=5), tetapi menurunkan precision karena data yang tidak relevan ikut masuk (Sroto Sokaraja pada K=5). Pada eksperimen ini, K=3 memberikan hasil yang semuanya relevan, sedangkan K=5 sudah memasukkan 1 dari 5 hasil yang salah kategori. Karena Qdrant tidak memakai batas skor minimum, aplikasi akan selalu mengembalikan tepat K hasil walaupun hasil terakhirnya tidak relevan. Nilai K yang terlalu besar perlu diimbangi dengan threshold skor atau filter `category`.

## Experiment 3 - Bad Retrieval

### Query

`minuman dingin yang tidak memakai santan`

### Actual Results

1. Es Teler (`minuman`), "... dicampur santan, sirup, susu kental manis, dan es."
2. Wedang Jahe (`minuman`), "Wedang jahe adalah minuman hangat ..."
3. Es Cendol (`minuman`), "... disiram santan, gula merah cair, dan es serut."

### Similarity Score

0.6953, 0.6926, 0.6513 (top_k = 3)

### Kenapa menurut kalian hasil tersebut kurang relevan?

Ketiga hasil justru kebalikan dari yang diminta. Es Teler dan Es Cendol memakai santan, padahal query meminta minuman tanpa santan, sedangkan Wedang Jahe memang tanpa santan tetapi merupakan minuman hangat, bukan minuman dingin. Yang membuat hasil ini menyesatkan adalah skornya justru lebih tinggi daripada hampir semua query yang hasilnya benar di Experiment 1. Jadi skor tinggi tidak berarti hasilnya benar.

### Menurut kalian apa yang mungkin menyebabkan hasil tersebut?

Embedding merangkum kalimat menjadi satu vector berdasarkan topik dan kata-kata yang muncul, sehingga kata negasi "tidak" hampir tidak berpengaruh. Query "minuman dingin yang tidak memakai santan" pada dasarnya diperlakukan seperti "minuman dingin + santan", dan data yang paling dekat adalah minuman dingin yang memang memakai santan. Wedang Jahe kemungkinan terangkat karena deskripsinya memuat kata "dingin" (dari frasa "cuaca dingin"), bukan karena minumannya dingin. Ini adalah keterbatasan umum embedding model berukuran kecil terhadap negasi dan atribut yang bertentangan.

Selain itu, ada beberapa retrieval lain yang juga kurang bagus dari pengujian yang sama:

| Query | Top-3 | Masalah |
|---|---|---|
| `kudapan yang terbuat dari ubi kayu` | Serabi (0.5553), Cireng (0.5508), Sate Madura (0.5434) | Getuk (dari singkong) tidak masuk top-3. Model gagal menyamakan "ubi kayu" dengan "singkong". Cireng (tapioka) baru relevan secara tidak langsung. |
| `jajanan manis yang isinya meleleh di mulut` | Gudeg (0.6795), Pempek (0.6019), Klepon (0.5750) | Jawaban yang benar (Klepon, "lumer saat digigit") baru di peringkat 3; Gudeg menang karena kata "manis". |
| `makanan khas Kalimantan` | Coto Makassar (0.6768), Sroto Sokaraja (0.6241), Serabi (0.5408) | Tidak ada makanan Kalimantan di dataset, tetapi aplikasi tetap mengembalikan hasil dengan skor tinggi. |
| `cara memperbaiki laptop yang tidak mau menyala` | Nasi Uduk (0.1131), Nasi Goreng (0.1120), Nasi Liwet (0.1017) | Query di luar topik tetap mendapat hasil, walaupun skornya sangat rendah. Di sini threshold sekitar 0.3 akan efektif, tetapi tidak akan menolong kasus Kalimantan. |

## Personal Reflection

### 1. Sebelum mengerjakan tugas ini, bagaimana kalian membayangkan sebuah search engine bekerja? Apakah ada perbedaan setelah mempelajari semantic search?

Sebelumnya saya membayangkan search engine mencocokkan kata kunci di query dengan kata yang ada di dokumen, lalu mengurutkan berdasarkan berapa banyak kata yang cocok. Setelah mengerjakan project ini, saya melihat bahwa semantic search bekerja dengan cara yang berbeda: dokumen dan query sama-sama diubah menjadi vector, lalu yang dicari adalah kedekatan makna. Buktinya query "olahan ikan dari Palembang yang dicocol saus asam" menemukan Pempek walaupun tidak ada satu pun kata "Palembang" atau "saus asam" di dataset.

### 2. Menurut kalian apa perbedaan terbesar antara keyword search dan semantic search?

Keyword search hanya menemukan dokumen yang memuat kata yang sama, tetapi hasilnya mudah dijelaskan dan presisi terhadap kata spesifik. Semantic search bisa menemukan sinonim, parafrase, bahkan lintas bahasa (query bahasa Inggris tentang Lombok menemukan Ayam Taliwang), tetapi bisa gagal di hal yang justru mudah bagi keyword search, seperti negasi ("tidak memakai santan") dan sinonim yang jarang ("ubi kayu" untuk "singkong"). Semantic search juga selalu mengembalikan hasil, bahkan untuk query yang tidak ada jawabannya.

### 3. Menurut kalian apa fungsi embedding di dalam semantic search?

Embedding adalah representasi makna dalam bentuk angka. Tanpa embedding, komputer tidak bisa menghitung seberapa mirip dua kalimat secara makna. Dengan embedding, kemiripan itu menjadi perhitungan cosine similarity antara dua vector berukuran 384.

### 4. Kenapa embedding tidak cukup hanya disimpan di list Python jika jumlah data menjadi sangat banyak?

List Python berada di RAM dan hilang ketika program berhenti, sehingga embedding harus dihitung ulang setiap kali server dinyalakan. Pencarian di list juga brute force: query harus dibandingkan dengan semua vector satu per satu (O(N·d) per query), dan ini menjadi lambat untuk jutaan data. Vector database seperti Qdrant menyimpan data secara persisten, dan pada mode server memakai index approximate nearest neighbor (HNSW) agar pencarian tetap cepat pada data besar. Qdrant juga menyediakan payload serta filter metadata yang tidak dimiliki list biasa. Mode lokal (`QdrantClient(path=...)`) yang dipakai di project ini cocok untuk pengembangan dengan data kecil; untuk data besar, Qdrant sebaiknya dijalankan sebagai server.

### 5. Bagian project mana yang paling sulit kalian pahami?

Bagian yang paling sulit adalah membaca arti similarity score. Awalnya saya mengira skor di atas 0.6 berarti hasilnya pasti benar, tetapi pada query "minuman dingin yang tidak memakai santan" skornya 0.6953 sementara hasilnya salah, sedangkan Rawon yang benar hanya 0.5612. Ternyata skor hanya bermakna relatif di dalam satu query, bukan sebagai ukuran benar atau salah yang absolut.

### 6. Bagian kode mana yang paling banyak dibantu oleh AI?

Endpoint `POST /index` dan `POST /search` di `main.py`, terutama bagian pembuatan `PointStruct` dan pemanggilan `client.query_points`, serta script `experiments/run_experiments.py`.

### 7. Jelaskan dengan bahasa kalian sendiri bagaimana bagian kode tersebut bekerja.

Di `/index`, semua `text` dari dataset di-encode sekaligus (`model.encode(texts)`) sehingga menghasilkan 36 vector. Setiap vector dipasangkan dengan datanya menjadi `PointStruct(id, vector, payload)` lalu dikirim ke Qdrant dengan `upsert`. ID memakai nomor urut data, sehingga jika `/index` dipanggil dua kali, data lama ditimpa dan tidak menjadi ganda. Di `/search`, query di-encode menjadi satu vector, lalu `query_points` meminta Qdrant mencari `limit=top_k` point terdekat. Jika ada `category`, ditambahkan `Filter` agar pencarian hanya dilakukan pada payload dengan kategori tersebut. Hasilnya diubah menjadi list berisi payload dan `point.score`.

### 8. Menurut kalian, aplikasi semantic search yang kalian buat bisa dikembangkan menjadi aplikasi apa jika project ini dilanjutkan?

Rekomendasi menu untuk aplikasi pemesanan makanan atau UMKM kuliner, di mana pembeli bisa mengetik keinginan seperti "yang hangat dan tidak pedas" lalu mendapatkan menu yang cocok. Untuk itu perlu ditambahkan hybrid search (gabungan keyword dan semantic) dan filter metadata seperti `region`, karena eksperimen menunjukkan semantic search murni lemah terhadap negasi dan atribut spesifik.

## AI Usage

### AI tools yang digunakan

Claude (Anthropic).

### AI digunakan untuk membantu bagian apa?

Membuat struktur kode `main.py`, dataset `data.json`, script eksperimen otomatis `experiments/run_experiments.py`, serta menyusun draf README ini dari hasil eksperimen.

### Bagian apa yang kalian ubah atau tentukan sendiri setelah mendapatkan hasil dari AI?

Saya menjalankan seluruh eksperimen di laptop sendiri sehingga semua skor di README ini adalah actual output aplikasi (`experiments/results.json`). Dari 7 query Experiment 1 dan 5 kandidat bad retrieval, saya memilih mana yang dimasukkan berdasarkan hasil yang benar-benar keluar, lalu memeriksa ulang interpretasi setiap hasil terhadap isi dataset.
