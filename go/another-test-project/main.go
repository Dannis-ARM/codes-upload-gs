package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
)

// 定义结构体来映射 JSON 响应中的单个项目 (Post)
// 结构体字段后的 `json:"..."` 标签告诉 Go 的 json 包
// 如何将 JSON 键映射到 Go 结构体字段。
type Post struct {
	UserID int    `json:"userId"`
	ID     int    `json:"id"`
	Title  string `json:"title"`
	Body   string `json:"body"`
}

func main() {
	// 1. 定义 API 端点
	apiURL := "https://jsonplaceholder.typicode.com/posts"
	
	fmt.Printf("正在调用 API: %s\n", apiURL)
	
	// 2. 发起 HTTP GET 请求
	response, err := http.Get(apiURL)
	if err != nil {
		log.Fatalf("发起 HTTP 请求失败: %v", err)
		return
	}
	// 确保在函数退出时关闭响应体，释放资源
	defer response.Body.Close()

	// 3. 检查 HTTP 状态码
	if response.StatusCode != http.StatusOK {
		log.Fatalf("API 调用失败，状态码: %d", response.StatusCode)
		return
	}

	// 4. 读取响应体
	body, err := io.ReadAll(response.Body)
	if err != nil {
		log.Fatalf("读取响应体失败: %v", err)
		return
	}

	// 5. 解析 JSON 数据到结构体切片
	// 因为 API 响应是一个 JSON 对象数组 ([]Post)
	var posts []Post
	err = json.Unmarshal(body, &posts)
	if err != nil {
		log.Fatalf("JSON 解析失败: %v", err)
		return
	}

	fmt.Println("---")
	fmt.Printf("成功获取到 %d 篇文章。\n", len(posts))
	fmt.Println("---")
	
	// 6. 使用 for 循环遍历每个项目并打印信息
	// posts 是一个切片，我们可以使用 `range` 循环遍历它。
	// `i` 是索引，`post` 是当前循环中的 Post 结构体实例。
	for i, post := range posts {
		// 打印前 5 篇文章的信息作为示例
		if i < 5 {
			fmt.Printf("文章 #%d (ID: %d) - 标题: %s\n", i+1, post.ID, post.Title)
		} else if i == 5 {
			// 只打印前 5 个，避免输出过多内容
			fmt.Println("...")
			fmt.Printf("（总共还有 %d 篇文章未显示）\n", len(posts) - 5)
			break 
		}
	}
}