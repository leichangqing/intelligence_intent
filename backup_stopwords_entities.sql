-- MySQL dump 10.13  Distrib 8.0.30, for macos12 (x86_64)
--
-- Host: localhost    Database: intent_db
-- ------------------------------------------------------
-- Server version	8.0.30

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `stop_words`
--

DROP TABLE IF EXISTS `stop_words`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `stop_words` (
  `id` int NOT NULL AUTO_INCREMENT,
  `word` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '停用词',
  `category` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '分类',
  `language` varchar(10) COLLATE utf8mb4_unicode_ci DEFAULT 'zh' COMMENT '语言',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否激活',
  `created_by` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建人',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `word` (`word`),
  KEY `idx_word` (`word`),
  KEY `idx_category` (`category`),
  KEY `idx_language` (`language`),
  KEY `idx_active` (`is_active`)
) ENGINE=InnoDB AUTO_INCREMENT=54 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='停用词表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `stop_words`
--

LOCK TABLES `stop_words` WRITE;
/*!40000 ALTER TABLE `stop_words` DISABLE KEYS */;
INSERT INTO `stop_words` VALUES (1,'的','particle','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(2,'了','particle','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(3,'在','preposition','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(4,'是','verb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(5,'有','verb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(6,'和','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(7,'就','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(8,'不','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(9,'人','noun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(10,'都','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(11,'一','number','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(12,'个','classifier','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(13,'上','preposition','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(14,'也','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(15,'很','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(16,'到','verb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(17,'说','verb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(18,'要','verb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(19,'去','verb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(20,'来','verb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(21,'可以','verb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(22,'这','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(23,'那','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(24,'我','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(25,'你','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(26,'他','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(27,'她','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(28,'它','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(29,'我们','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(30,'你们','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(31,'他们','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(32,'什么','pronoun','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(33,'如何','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(34,'怎么','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(35,'为什么','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(36,'这样','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(37,'那样','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(38,'现在','time','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(39,'以后','time','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(40,'以前','time','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(41,'今天','time','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(42,'明天','time','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(43,'昨天','time','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(44,'已经','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(45,'还','adverb','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(46,'但','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(47,'但是','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(48,'而且','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(49,'或者','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(50,'因为','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(51,'所以','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(52,'如果','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(53,'虽然','conjunction','zh',1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08');
/*!40000 ALTER TABLE `stop_words` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `entity_patterns`
--

DROP TABLE IF EXISTS `entity_patterns`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `entity_patterns` (
  `id` int NOT NULL AUTO_INCREMENT,
  `pattern_name` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '模式名称',
  `pattern_regex` text COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '正则表达式',
  `entity_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '实体类型',
  `description` text COLLATE utf8mb4_unicode_ci COMMENT '描述',
  `examples` json DEFAULT NULL COMMENT '示例',
  `confidence` decimal(5,4) DEFAULT '0.9000' COMMENT '置信度',
  `is_active` tinyint(1) DEFAULT '1' COMMENT '是否激活',
  `priority` int DEFAULT '1' COMMENT '优先级',
  `created_by` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '创建人',
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `pattern_name` (`pattern_name`),
  KEY `idx_pattern_name` (`pattern_name`),
  KEY `idx_entity_type` (`entity_type`),
  KEY `idx_active` (`is_active`),
  KEY `idx_priority` (`priority`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='实体识别模式表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `entity_patterns`
--

LOCK TABLES `entity_patterns` WRITE;
/*!40000 ALTER TABLE `entity_patterns` DISABLE KEYS */;
INSERT INTO `entity_patterns` VALUES (1,'手机号码','1[3-9]\\d{9}','PHONE','中国大陆手机号码','\"[\\\"13800138000\\\", \\\"18912345678\\\"]\"',0.9500,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(2,'邮箱地址','[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}','EMAIL','电子邮箱地址','\"[\\\"example@email.com\\\", \\\"user@domain.com\\\"]\"',0.9000,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(3,'身份证号','\\d{15}|\\d{18}','ID_CARD','身份证号码','\"[\\\"110101199001011234\\\", \\\"11010119900101123X\\\"]\"',0.9500,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(4,'银行卡号','\\d{16,19}','BANK_CARD','银行卡号','\"[\\\"6222080012345678\\\", \\\"62220800123456789\\\"]\"',0.9000,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(5,'金额','[0-9,]+(?:\\.[0-9]+)?(?:元|块|万|千|百)?','AMOUNT','金额表达','\"[\\\"100元\\\", \\\"1000块\\\", \\\"1.5万\\\"]\"',0.8500,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(6,'日期','\\d{4}[-/年]\\d{1,2}[-/月]\\d{1,2}[日号]?','DATE','日期表达','\"[\\\"2024-01-01\\\", \\\"2024年1月1日\\\"]\"',0.8500,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(7,'时间','\\d{1,2}[:|：]\\d{1,2}','TIME','时间表达','\"[\\\"14:30\\\", \\\"上午9点\\\"]\"',0.8000,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(8,'航班号','[A-Z]{2}\\d{3,4}','FLIGHT','航班号','\"[\\\"CA1234\\\", \\\"MU5678\\\"]\"',0.9500,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(9,'机场代码','[A-Z]{3}','AIRPORT','三字机场代码','\"[\\\"PEK\\\", \\\"SHA\\\", \\\"CAN\\\"]\"',0.9000,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08'),(10,'中国城市','[北京|上海|广州|深圳|杭州|南京|武汉|成都|西安|重庆|天津|青岛|大连|厦门|苏州|无锡|宁波|长沙|郑州|济南|哈尔滨|沈阳|长春|石家庄|太原|呼和浩特|兰州|西宁|银川|乌鲁木齐|拉萨|昆明|贵阳|南宁|海口|三亚|福州|南昌|合肥]+','CITY','中国主要城市','\"[\\\"北京\\\", \\\"上海\\\", \\\"广州\\\"]\"',0.8500,1,1,'system','2025-07-31 02:09:08','2025-07-31 02:09:08');
/*!40000 ALTER TABLE `entity_patterns` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2025-07-31 10:15:12
