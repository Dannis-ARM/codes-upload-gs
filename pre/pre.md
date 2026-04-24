"Thanks for the detailed explanation. This is Yuyang from the <> team. In the rest of the presentation, I am going to walk you through the exact benefits we gained from choosing Cloud instead of on-prem deployment. Also, I will cover the challenges we met, achibemetn we made.

## **Page 5: Architecture & Security**

Firstly "Let’s talk about what PCA is **So full service naem is Aws Certificate Manager - Private certifacte authority* Its job is to sign and issue the certificates that enryp on trasint encrpiton every China service which  within our firm.

why we chose a cloud-native solution over a traditional one. 
**Cloud bring hightest safty out of box.** see from the graph on the right, we built the infrastructure using a two-layer architecture: a Root CA used to sign the Intermediate CA, and the Intermediate CA which handles the actual issuing. their msters keys are most imoprtant secrest taht need high protection. Aws forced keys to stay in an AWS-managed physical vault—a Hardware Security Module (HSM) where keys are 'burned' into the chip and **never** leave that hardware boundary. Even if someone were to physically breach the data center and steal the hardware, they would not be able to decipher the secrets. This is because the AWS hardware would detect the intrusion and **self-destruct** the keys. From the very beginning, Cloud PCA has natively met our security and regulatory requirements.

**Next is Reliability and Availability boost.** Suppose we choose onprem dployment. Then we faced data center constraints because in our current onprem setups, we have two regions. but we only had a single AZ (Availability Zone) (datacenter) per region. This meant failover had to happen at a regional level; switching traffic between Shanghai and Beijing when a disaster occurred will at least cause a few **minutes** of downtime. But choosing AWS, we can leverage **Multi-AZ redundancy**. With three AZ in each region, the recovery time has been slashed **from minutes to seconds.**

**High Reliability & availability cannot be achieved by PCA servers alone; we need make sure the data always be accessible too.** There are canceled certificate is granted to an unwanted domain, we need to cert is valid or revoked. otherwise we exposed to clients and facing reputation damage. This brings us to the storage of the Certificate Revocation List (CRL). 

we leverage **S3 Buckets**. By using S3, we gain **'11 nines' of data durability.** To put that in detail: if you store 10 million blocked certificates, you would expect to lose only one every 10,000 years. Furthermore, S3 ensures our blacklist is **distributed** across multiple AZ. Ensuring it's always be accsible.

"**Last point,  Operational Excellence. & monitoring** By choosing the cloud, we no longer need to deal with the overhead of **managing DC nodes directly**.  OS patching, hardware scaling, and backup, secrets rotations are gone. The backend servers are fully managed by AWS; we treat the entire PCA service as one whole entity. By heavy lifting' infra maintenance burden to the cloud provider, our engineering talent is freed to focus entirely on **business logic**.

Monitoring will be much frindedl to use in cloud **CloudWatch can be used out of box** CloudWatch is like a eye will check real-time telemetry on our PCA’s health status. The alerts notify us of any certificate expiration or anomoly oocur.
---

## **Page 6: The Strategy - Why Service Catalog?**

"Let's go deeper into *how* we handle IaC deployment. You might think: we have GSCloud on-prem, and we have SkyFoundry and FastTrack on Cloud, so why do we need to talk about IaC governance?

The reality is that we have chanlenegs on **'Governance Gap'** in the China environment. the safty controls and gruardrail that block risky TF code before it runs are missnig here. Years ago, we didn't have the Gitlab, SDLC nor guardrails. Without those controles, using raw TF code is a massive risk . Users might mistakenly create a PCA that allows unauthorized domains, or create an S3 bucket policy that allows anyone to update the CRL list. We need a solution that both flexible and safe to use.

This is when **AWS Service Catalog** comes to help, 
Service Catalog acts as our governance layer, bridging the Iac codes and Guarreails. SC "It’s powered by **CloudFormation**. In case you’ve never heard of it, think of CloudFormation as a **'Blueprint'**—defined using either JSON or YAML—that can provisions any cloud ressouces. Version contorl, dependecy, roolbacck

**Service Catalog** wrapping these cloudformation blueprints with security requirements. such as KMS encryption and strict S3 Bucket Policies—is already **'baked'** into the template.

Users no longer need to worry about whether their policy 'writing' is secure enough, because our **Tech Risk**  carefully helped reviewed and approved the underlying templates. users, they simply select the pre-approved product from the catalog, add it to their **'shopping cart,'** and check out to deploy."  fully compliant Private CAs and S3 buckets.
---

## **Part 7: Global Collaboration & Access Control**

"Lastly, let’s talk about how we empower our **PKI Team** in their deployment and maintenance. With help from our offshore peers, we localized **\<XXX\>**, which acts as the broker to map on-premise identities to cloud roles. In this way, you are granted specific cloud permissions, such as creating audit reports or issuing certificates.

As seen in the graph on the right, we’ve designed two  workflows for our onshore and offshore cloud urers:

* **For our Onshore Team:** The process is straightforward. Onshore users use **CI/CD pipelines** to push deployment scripts. Using the system account, they obtain temporary credentials from **\<XXX\>** to deploy resources.
* **For our Offshore Experts:** We have an additional layer required by China's regulatory framework—overseas access requires domestic approval. We partnered with the Windows Team to utilize **Lockdown Desktops**. This provides a secure, isolated environment where offshore colleagues log in, fetch a lease, and then launch the same CI/CD pipelines to manage deployments.

By localizing **\<XXX\>** and integrating it with China systems, we enable users to have smooth and complint development.